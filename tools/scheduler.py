"""
Cỗ máy Lập lịch Tự động Hóa Quỹ (Fund Automated Scheduler).
Chạy ngầm trong Docker container hoặc máy tính cá nhân để thực thi:
- 08:00 AM (T2 - T6): Bản tin Tiền thị trường & Watchlist sáng
- 15:30 PM (T2 - T6): Chốt sổ Kế toán NAV Ngày (Mark-to-Market)
- 20:00 PM (T2 - T6): Đối soát giao dịch với Bạn (Evening Reconciliation)
- 21:00 PM (T2 - T6): Đồng bộ nến ngày mới nhất từ BigQuery về Parquet 5 năm
"""

import time
import asyncio
from datetime import datetime
from pathlib import Path
import sys

# Thêm thư mục gốc vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings
from database.db_manager import DatabaseManager
from tools.parquet_manager import ParquetMarketDataManager
from tools.bigquery_sync import BigQuerySyncEngine
from interfaces.telegram_bot import FundTelegramBot
from interfaces.message_templates import TelegramMessageFormatter

class FundScheduler:
    """Quản trị viên Lập lịch Tự động của Quỹ Đầu tư AI"""

    def __init__(self):
        self.db = DatabaseManager()
        self.parquet_mgr = ParquetMarketDataManager()
        self.bq_sync = BigQuerySyncEngine()
        self.bot = FundTelegramBot() if settings.TELEGRAM_BOT_TOKEN else None

    async def run_morning_job(self):
        """08:00 AM: Bản tin Sáng & Quét Watchlist nổ Vol"""
        print(f"\n[SCHEDULER {datetime.now().strftime('%H:%M:%S')}] ☀️ Đang chạy Morning Briefing...")
        candidates = self.parquet_mgr.scan_breakout_vol_candidates(min_vol_ratio=1.2, limit=5)
        
        msg = (
            "☀️ <b>BẢN TIN TIỀN THỊ TRƯỜNG (08:00 AM)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• Trạng thái đề xuất: <b>[SIDEWAY / CHỌN LỌC]</b>\n"
            "• Khuyến nghị: Ưu tiên cổ phiếu bứt phá nền giá có dòng tiền xác nhận.\n\n"
        )
        if candidates:
            msg += "🎯 <b>TOP CỔ PHIẾU ĐỘT BIẾN VOLUME CẦN THEO DÕI:</b>\n"
            for c in candidates:
                msg += f"• <b>{c['ticker']}</b>: Giá {c['close']:,.2f} | Vol: <code>{c['vol_ratio']}x</code> | Trên MA20: <code>+{c['diff_ma20_pct']}%</code>\n"
        else:
            msg += "ℹ️ Phiên gần nhất chưa có mã đột biến thanh khoản đặc biệt."

        if self.bot and self.bot.chat_id:
            try:
                app = self.bot.build_application()
                await app.bot.send_message(chat_id=self.bot.chat_id, text=msg, parse_mode="HTML")
                print("✅ Đã gửi Morning Briefing qua Telegram.")
            except Exception as e:
                print(f"⚠️ Không thể gửi Telegram: {e}")

    async def run_eod_job(self):
        """15:30 PM: Chốt sổ Kế toán NAV Ngày"""
        print(f"\n[SCHEDULER {datetime.now().strftime('%H:%M:%S')}] 🌙 Đang chốt sổ Kế toán NAV...")
        today_str = datetime.now().strftime("%Y-%m-%d")
        prices = self.parquet_mgr.get_latest_close_prices()

        nav_res = self.db.close_daily_nav(
            trade_date=today_str,
            current_prices=prices,
            notes="Chốt sổ tự động 15:30 qua Scheduler"
        )
        print(f"✅ Đã chốt sổ NAV: {nav_res['total_nav']:,.0f} VND (Biến động: {nav_res['daily_pnl']:+,.0f} VND)")

        if self.bot and self.bot.chat_id:
            try:
                msg = TelegramMessageFormatter.format_nav_summary(nav_res)
                app = self.bot.build_application()
                await app.bot.send_message(chat_id=self.bot.chat_id, text=msg, parse_mode="HTML")
            except Exception as e:
                print(f"⚠️ Không thể gửi Telegram NAV: {e}")

    async def run_evening_reconciliation_job(self):
        """20:00 PM: Nhắc nhở Đối soát Lệnh chưa khớp"""
        print(f"\n[SCHEDULER {datetime.now().strftime('%H:%M:%S')}] 🔔 Kiểm tra đối soát lệnh chờ...")
        with self.db.get_connection() as conn:
            pending = conn.execute("""
                SELECT order_id, ticker, action, proposed_price, proposed_volume
                FROM order_history
                WHERE status IN ('PROPOSED', 'SUBMITTED', 'PENDING_RECONCILIATION')
                ORDER BY created_at DESC;
            """).fetchall()

        if pending and self.bot and self.bot.chat_id:
            pending_list = [dict(r) for r in pending]
            msg = TelegramMessageFormatter.format_evening_check(pending_list)
            try:
                app = self.bot.build_application()
                await app.bot.send_message(chat_id=self.bot.chat_id, text=msg, parse_mode="HTML")
                print(f"✅ Đã gửi nhắc nhở đối soát {len(pending)} lệnh chờ.")
            except Exception as e:
                print(f"⚠️ Lỗi gửi đối soát: {e}")

    def run_nightly_sync_job(self):
        """21:00 PM: Đồng bộ nến ngày từ BigQuery về Parquet 5 năm"""
        print(f"\n[SCHEDULER {datetime.now().strftime('%H:%M:%S')}] 📥 Đang đồng bộ nến ngày từ BigQuery...")
        success = self.bq_sync.sync_incremental_daily(days=3)
        if success:
            print("✅ Đồng bộ dữ liệu đêm thành công!")
        else:
            print("ℹ️ Quá trình đồng bộ kết thúc (không có nến mới hoặc chưa có kết nối).")

    async def start_loop(self):
        """Vòng lặp giám sát thời gian thực tế"""
        print("⏰ CỖ MÁY LẬP LỊCH QUỸ ĐẦU TƯ AI ĐÃ BẬT HOẠT ĐỘNG (24/7)...")
        print("📋 Lịch trình tự động (Thứ 2 đến Thứ 6):")
        print("   • 08:00 AM: Bản tin Sáng & Quét Watchlist nổ Vol")
        print("   • 15:30 PM: Chốt sổ Kế toán NAV Ngày")
        print("   • 20:00 PM: Đối soát Lệnh chưa xác nhận")
        print("   • 21:00 PM: Đồng bộ nến ngày từ BigQuery")

        last_executed = {
            "morning": None,
            "eod": None,
            "reconcile": None,
            "sync": None
        }

        while True:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            weekday = now.weekday()  # 0: Thứ 2, 4: Thứ 6

            if weekday < 5:  # Chỉ chạy trong ngày giao dịch (T2 - T6)
                # 1. 08:00 AM
                if now.hour == 8 and now.minute == 0 and last_executed["morning"] != today_str:
                    await self.run_morning_job()
                    last_executed["morning"] = today_str

                # 2. 15:30 PM
                elif now.hour == 15 and now.minute == 30 and last_executed["eod"] != today_str:
                    await self.run_eod_job()
                    last_executed["eod"] = today_str

                # 3. 20:00 PM
                elif now.hour == 20 and now.minute == 0 and last_executed["reconcile"] != today_str:
                    await self.run_evening_reconciliation_job()
                    last_executed["reconcile"] = today_str

                # 4. 21:00 PM
                elif now.hour == 21 and now.minute == 0 and last_executed["sync"] != today_str:
                    self.run_nightly_sync_job()
                    last_executed["sync"] = today_str

            # Nghỉ 30 giây trước khi kiểm tra lại
            await asyncio.sleep(30)

def main():
    scheduler = FundScheduler()
    asyncio.run(scheduler.start_loop())

if __name__ == "__main__":
    main()

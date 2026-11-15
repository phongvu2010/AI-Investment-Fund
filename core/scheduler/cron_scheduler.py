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
from core.accounting.db_manager import DatabaseManager
from core.data.parquet_manager import ParquetMarketDataManager
from core.data.bigquery_sync import BigQuerySyncEngine
from core.data.intraday_data_feed import IntradayDataFeed
from ai_brain.engines.jev_decision_engine import JevDecisionEngine
from apps.bot.telegram_bot import FundTelegramBot
from apps.bot.message_templates import TelegramMessageFormatter

class FundScheduler:
    """Quản trị viên Lập lịch Tự động của Quỹ Đầu tư AI"""

    def __init__(self):
        self.db = DatabaseManager()
        self.parquet_mgr = ParquetMarketDataManager()
        self.bq_sync = BigQuerySyncEngine()
        self.intraday_feed = IntradayDataFeed()
        self.jev = JevDecisionEngine()
        self.bot = FundTelegramBot() if settings.TELEGRAM_BOT_TOKEN else None

    async def run_morning_job(self):
        """08:00 AM: Bản tin Sáng & Quét Watchlist nổ Vol kết hợp Jev System 1 Triage"""
        print(f"\n[SCHEDULER {datetime.now().strftime('%H:%M:%S')}] ☀️ Đang chạy Morning Briefing...")
        candidates = self.parquet_mgr.scan_breakout_vol_candidates(min_vol_ratio=1.2, limit=5)
        
        msg = (
            "☀️ <b>BẢN TIN TIỀN THỊ TRƯỜNG (08:00 AM)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• Trạng thái đề xuất: <b>[SIDEWAY / CHỌN LỌC]</b>\n"
            "• Khuyến nghị: Ưu tiên cổ phiếu bứt phá nền giá có dòng tiền xác nhận.\n\n"
        )
        if candidates:
            msg += "🎯 <b>TOP CỔ PHIẾU ĐỘT BIẾN VOLUME (JEV AI SYSTEM 1 TRIAGED):</b>\n"
            for c in candidates:
                triage = self.jev.triage_market_event(
                    c["ticker"],
                    intraday_bar={"pct_change": c["diff_ma20_pct"], "vol_ratio": c["vol_ratio"]}
                )
                route = self.jev.route_strategy_book(c["ticker"])
                t_tag = "MATERIAL" if triage.value else "NOISE"
                msg += f"• <b>{c['ticker']}</b>: Giá {c['close']:,.2f} | Vol: <code>{c['vol_ratio']}x</code> | Jev: <code>[{t_tag} -> {route.value}]</code>\n"
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

    async def run_intraday_risk_job(self):
        """14:15 PM: Quét Rủi ro Giữa phiên & Cảnh báo Sớm trước giờ ATC (T+2.5 & Floor-Lock Early-Warning)"""
        print(f"\n[SCHEDULER {datetime.now().strftime('%H:%M:%S')}] 🚨 Đang quét Rủi ro Giữa phiên & Kiểm tra Kẹt Sàn (14:15 PM)...")
        portfolio = self.db.get_portfolio()
        if not portfolio:
            print("ℹ️ Danh mục hiện đang 100% tiền mặt, không có vị thế rủi ro.")
            return

        prices = self.parquet_mgr.get_latest_close_prices()
        alerts = []

        for p in portfolio:
            ticker = p["ticker"]
            avg_price = p["avg_buy_price"]
            book = p.get("strategy_book", "QUANT")

            # Ưu tiên lấy giá Live từ IntradayDataFeed đa nguồn
            live_bar = self.intraday_feed.get_live_bar(ticker)
            if live_bar:
                curr_price = live_bar["close"]
                source_tag = live_bar.get("source", "LIVE")
            else:
                curr_price = prices.get(ticker, avg_price)
                source_tag = "EOD"

            norm_curr = curr_price * 1000.0 if curr_price < 1000.0 else curr_price
            pnl_pct = ((norm_curr - avg_price) / avg_price) * 100.0 if avg_price > 0 else 0.0

            # 1. Kiểm tra Cực đoan: RỦI RO KẸT SÀN / TRẮNG BÊN MUA (Floor-Lock Shock)
            floor_risk = self.intraday_feed.check_floor_lock_risk(ticker)
            if floor_risk.get("is_floor_locked", False):
                alerts.append({
                    "ticker": ticker,
                    "book": book,
                    "pnl_pct": pnl_pct,
                    "severity": "EMERGENCY_FLOOR_LOCKED",
                    "msg": f"Mã {ticker} ĐANG KẸT SÀN / TRẮNG BÊN MUA (Giá {curr_price:,.2f}, Sàn {floor_risk.get('floor_price', 0):,.2f}). Lệnh MP thông thường KHÔNG THỂ KHỚP! Khuyến nghị: Chuẩn bị kê lệnh sớm ATO phiên sáng mai hoặc mở vị thế Short Phái sinh VN30F1M để phòng vệ danh mục (Delta Hedging)."
                })
                continue
            elif floor_risk.get("is_near_floor", False):
                alerts.append({
                    "ticker": ticker,
                    "book": book,
                    "pnl_pct": pnl_pct,
                    "severity": "CRITICAL",
                    "msg": f"Mã {ticker} TIỆM CẬN SÀN (< 1.5% giá sàn). Nguy cơ trắng bên mua khi vào ATC. Khuyến nghị: Chủ động hạ tỷ trọng ngay trước 14:25 tránh bị đóng băng thanh khoản."
                })
                continue

            # 2. Cảnh báo rủi ro cắt lỗ thông thường
            if book == "QUANT" and pnl_pct <= -5.0:
                alerts.append({
                    "ticker": ticker,
                    "book": book,
                    "pnl_pct": pnl_pct,
                    "severity": "CRITICAL" if pnl_pct <= -6.5 else "HIGH",
                    "msg": f"Mã {ticker} (Sổ QUANT, nguồn {source_tag}) giảm {pnl_pct:.2f}% (Tiệm cận ngưỡng dừng lỗ -7.0%). Khuyến nghị: Chuẩn bị lệnh MP/LO bán trước ATC."
                })
            elif book == "CORE" and pnl_pct <= -10.0:
                alerts.append({
                    "ticker": ticker,
                    "book": book,
                    "pnl_pct": pnl_pct,
                    "severity": "HIGH",
                    "msg": f"Mã {ticker} (Sổ CORE, nguồn {source_tag}) giảm {pnl_pct:.2f}% (Tiệm cận ngưỡng dừng lỗ -15.0%). Khuyến nghị: Rà soát lại biến số cơ bản."
                })
            elif pnl_pct >= 15.0 and book == "QUANT":
                alerts.append({
                    "ticker": ticker,
                    "book": book,
                    "pnl_pct": pnl_pct,
                    "severity": "INFO",
                    "msg": f"Mã {ticker} (Sổ QUANT) đạt mức sinh lời {pnl_pct:+.2f}%. Khuyến nghị: Chủ động hiện thực hóa 50% lợi nhuận."
                })

            # 3. Chấm điểm rủi ro thực thi Jev AI System 1
            nav_data = self.db.get_latest_nav() or {}
            risk_score = self.jev.score_execution_risk(
                ticker=ticker,
                action="SELL",
                proposed_vol=int(p.get("quantity", 0)),
                portfolio_state={
                    "total_nav": nav_data.get("total_nav", settings.INITIAL_CAPITAL),
                    "current_position_value": p.get("market_value", 0.0),
                    "strategy_book": book,
                    "available_quantity": int(p.get("quantity", 0))
                }
            )
            if risk_score.value > 0.70:
                alerts.append({
                    "ticker": ticker,
                    "book": book,
                    "pnl_pct": pnl_pct,
                    "severity": "CRITICAL",
                    "msg": f"Jev AI phát hiện rủi ro thực thi cao ({risk_score.value:.2f}/1.00): {risk_score.reasoning}"
                })

        if alerts and self.bot and self.bot.chat_id:
            msg = (
                "🚨 <b>CẢNH BÁO RỦI RO TRƯỚC PHIÊN ATC (14:15 PM)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "<i>Hệ thống phát hiện biến động danh mục cần xử lý ngay trước 14:30:</i>\n\n"
            )
            for a in alerts:
                if a["severity"] == "EMERGENCY_FLOOR_LOCKED":
                    icon = "⛔"
                elif a["severity"] == "CRITICAL":
                    icon = "🔥"
                elif a["severity"] == "HIGH":
                    icon = "⚠️"
                else:
                    icon = "🎯"
                msg += f"{icon} <b>[{a['book']}] {a['ticker']}</b> ({a['pnl_pct']:+.2f}%)\n"
                msg += f"   • {a['msg']}\n\n"
            
            msg += "⚡ <i>Vui lòng kiểm tra app CTCK để chủ động cơ cấu trước giờ ATC!</i>"

            try:
                app = self.bot.build_application()
                await app.bot.send_message(chat_id=self.bot.chat_id, text=msg, parse_mode="HTML")
                print(f"✅ Đã gửi {len(alerts)} cảnh báo rủi ro 14:15 qua Telegram.")
            except Exception as e:
                print(f"⚠️ Không thể gửi Telegram cảnh báo 14:15: {e}")
        else:
            print(f"✅ Rà soát 14:15: Toàn bộ {len(portfolio)} vị thế trong danh mục đều nằm trong ngưỡng an toàn.")

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
        print("   • 14:15 PM: Quét Rủi ro Giữa phiên & Cảnh báo Sớm trước ATC")
        print("   • 15:30 PM: Chốt sổ Kế toán NAV Ngày")
        print("   • 20:00 PM: Đối soát Lệnh chưa xác nhận")
        print("   • 21:00 PM: Đồng bộ nến ngày từ BigQuery")

        last_executed = {
            "morning": None,
            "intraday": None,
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

                # 2. 14:15 PM (Pre-ATC Early Warning)
                elif now.hour == 14 and now.minute == 15 and last_executed["intraday"] != today_str:
                    await self.run_intraday_risk_job()
                    last_executed["intraday"] = today_str

                # 3. 15:30 PM
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

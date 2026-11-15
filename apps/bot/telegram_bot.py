"""
Module Telegram Bot (Giao diện Tương tác Di động của Quỹ).
Hỗ trợ:
- Gửi Tờ trình đầu tư kèm nút bấm xác nhận [Đã khớp chuẩn] / [Báo khớp khác] / [Từ chối]
- Tra cứu NAV và Danh mục (0 Token)
- Lệnh /fill nhập bù linh hoạt
- Bộ phân tích văn bản tự nhiên (Regex Parser)
"""

import re
import sys
import asyncio
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any

# Tự động thêm thư mục gốc dự án vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from config import settings
from core.accounting.db_manager import DatabaseManager
from apps.bot.message_templates import TelegramMessageFormatter

class FundTelegramBot:
    """Bot Telegram đóng vai trò Trợ lý Khớp lệnh và Thông tin Quỹ"""

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.db = DatabaseManager()
        self.app = None

    def build_application(self) -> Application:
        """Khởi tạo Application Telegram với đầy đủ handlers"""
        if not self.token:
            raise ValueError("Chưa cấu hình TELEGRAM_BOT_TOKEN trong file .env")

        self.app = Application.builder().token(self.token).build()

        # Đăng ký các Command Handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("nav", self.cmd_nav))
        self.app.add_handler(CommandHandler("portfolio", self.cmd_portfolio))
        self.app.add_handler(CommandHandler("orders", self.cmd_orders))
        self.app.add_handler(CommandHandler("fill", self.cmd_fill))

        # Đăng ký Callback Query Handler (Nút bấm inline)
        self.app.add_handler(CallbackQueryHandler(self.handle_callback_query))

        # Đăng ký Text Message Handler (Bắt cú pháp tự nhiên)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))

        return self.app

    # ==========================================
    # COMMAND HANDLERS
    # ==========================================
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh chào mừng /start"""
        welcome_msg = (
            "🏛️ <b>CHÀO MỪNG BÁC ĐẾN VỚI HỆ THỐNG QUỸ ĐẦU TƯ AI!</b>\n\n"
            "Em là Bot Trợ lý Điều phối Giao dịch & Quản trị Danh mục.\n\n"
            "📌 <b>Các lệnh nhanh tra cứu (0 Token):</b>\n"
            "• <code>/nav</code> - Xem Tổng tài sản, tiền mặt, lãi/lỗ hôm nay\n"
            "• <code>/portfolio</code> - Xem danh mục cổ phiếu đang nắm giữ\n"
            "• <code>/orders</code> - Xem các lệnh gần nhất & lệnh đang chờ\n"
            "• <code>/fill MÃ SỐ_LƯỢNG GIÁ</code> - Nhập bù lệnh khớp thực tế\n"
            "• <code>/help</code> - Hướng dẫn chi tiết"
        )
        await update.message.reply_text(welcome_msg, parse_mode="HTML")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh hướng dẫn /help"""
        help_msg = (
            "📖 <b>HƯỚNG DẪN SỬ DỤNG BOT QUỸ ĐẦU TƯ:</b>\n\n"
            "1. <b>Khi có tín hiệu mua/bán mới:</b>\n"
            "AI sẽ gửi Tờ trình kèm nút bấm. Bác vào app CTCK đặt lệnh, khớp xong thì bấm nút <b>[ ĐÃ KHỚP CHUẨN]</b>.\n\n"
            "2. <b>Nếu khớp khác giá hoặc khối lượng:</b>\n"
            "Bác chỉ cần nhắn tin cú pháp nhanh:\n"
            "👉 <code>/fill HPG 5000 28.2</code>\n"
            "Hoặc nhắn tự nhiên: <code>khớp HPG 5000 giá 28.2</code>\n\n"
            "3. <b>Xem báo cáo tài chính quỹ:</b>\n"
            "Gõ <code>/nav</code> hoặc <code>/portfolio</code> bất kỳ lúc nào để xem số dư chuẩn xác."
        )
        await update.message.reply_text(help_msg, parse_mode="HTML")

    async def cmd_nav(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh tra cứu NAV /nav (0 Token)"""
        nav_info = self.db.get_latest_nav()
        if not nav_info:
            await update.message.reply_text("⚠️ Chưa có dữ liệu chốt sổ NAV.")
            return

        msg = TelegramMessageFormatter.format_nav_summary(nav_info)
        await update.message.reply_text(msg, parse_mode="HTML")

    async def cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh tra cứu danh mục /portfolio (0 Token)"""
        portfolio = self.db.get_portfolio()
        msg = TelegramMessageFormatter.format_portfolio_table(portfolio)
        await update.message.reply_text(msg, parse_mode="HTML")

    async def cmd_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh tra cứu sổ lệnh /orders (0 Token)"""
        with self.db.get_connection() as conn:
            rows = conn.execute("""
                SELECT order_id, ticker, action, proposed_price, proposed_volume,
                       executed_price, executed_volume, status, trade_date
                FROM order_history
                ORDER BY created_at DESC LIMIT 6;
            """).fetchall()

        if not rows:
            await update.message.reply_text("📭 Chưa có lệnh nào được tạo.")
            return

        msg = "📋 <b>LỊCH SỬ CÁC LỆNH GẦN NHẤT:</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for r in rows:
            st_icon = "✅" if r["status"] == "FILLED" else ("⏳" if r["status"] in ("PROPOSED", "SUBMITTED") else "⚪")
            act_color = "🟢" if r["action"] == "BUY" else "🔴"
            msg += (
                f"{st_icon} {act_color} <b>{r['ticker']}</b> ({r['action']}) - <code>{r['status']}</code>\n"
                f"   • Đề xuất: <code>{r['proposed_volume']:,} CP @ {r['proposed_price']:,.2f}</code>\n"
            )
            if r["executed_volume"]:
                msg += f"   • Đã khớp: <code>{r['executed_volume']:,} CP @ {r['executed_price']:,.2f}</code>\n"
            msg += f"   • Ngày: <code>{r['trade_date']}</code> | ID: <code>{r['order_id']}</code>\n\n"

        await update.message.reply_text(msg, parse_mode="HTML")

    async def cmd_fill(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Lệnh nhập bù /fill
        Cú pháp: /fill <TICKER> <VOLUME> <PRICE> [TRADE_DATE]
        Ví dụ: /fill HPG 5000 28.2
        """
        args = context.args
        if len(args) < 3:
            await update.message.reply_text(
                "⚠️ <b>Sai cú pháp!</b>\n"
                "Cú pháp đúng: <code>/fill MÃ KHỐI_LƯỢNG GIÁ [NGÀY]</code>\n"
                "Ví dụ: <code>/fill HPG 5000 28.2</code>",
                parse_mode="HTML"
            )
            return

        ticker = args[0].upper()
        strategy_book = "QUANT"
        trade_date_str = date.today().strftime("%Y-%m-%d")

        try:
            volume = int(args[1].replace(",", "").replace(".", ""))
            price = float(args[2].replace(",", "."))
            if len(args) > 3:
                for extra in args[3:]:
                    if extra.upper() in ("CORE", "QUANT"):
                        strategy_book = extra.upper()
                    elif re.match(r"^\d{4}-\d{2}-\d{2}$", extra):
                        trade_date_str = extra
        except ValueError:
            await update.message.reply_text("❌ Lỗi: Khối lượng hoặc Giá không đúng định dạng số!")
            return

        # Thực thi nhập bù vào Database
        try:
            order_id = self.db.record_retroactive_fill(
                ticker=ticker,
                action="BUY",
                executed_price=price,
                executed_volume=volume,
                trade_date=trade_date_str,
                notes=f"Nhập bù qua lệnh /fill trên Telegram ({strategy_book})",
                strategy_book=strategy_book
            )

            res_msg = (
                f"✅ <b>ĐÃ NHẬP BÙ THÀNH CÔNG!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• Mã lệnh: <code>{order_id}</code>\n"
                f"• Cổ phiếu: <b>{ticker}</b>\n"
                f"• Sổ chiến lược: <code>[{strategy_book}]</code>\n"
                f"• Khối lượng: <code>{volume:,} CP</code>\n"
                f"• Giá khớp: <code>{price:,.2f}</code>\n"
                f"• Ngày giao dịch: <code>{trade_date_str}</code>\n\n"
                f"💰 Danh mục và tiền mặt đã được cập nhật chuẩn xác!"
            )
            await update.message.reply_text(res_msg, parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi ghi nhận nhập bù: {str(e)}")

    # ==========================================
    # CALLBACK QUERY HANDLERS (NÚT BẤM INTERACTIVE)
    # ==========================================
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Xử lý sự kiện khi Bạn bấm các nút trên Telegram"""
        query = update.callback_query
        await query.answer()

        data = query.data
        parts = data.split(":")
        action_type = parts[0]
        order_id = parts[1] if len(parts) > 1 else ""

        if action_type == "fill_standard":
            # Bác bấm: [ ĐÃ KHỚP CHUẨN]
            with self.db.get_connection() as conn:
                order = conn.execute("SELECT * FROM order_history WHERE order_id = ?;", (order_id,)).fetchone()

            if not order:
                await query.edit_message_text("❌ Không tìm thấy thông tin lệnh này.")
                return

            if order["status"] == "FILLED":
                await query.edit_message_text(f"ℹ️ Lệnh <code>{order_id}</code> đã được xác nhận khớp trước đó rồi ạ.", parse_mode="HTML")
                return

            # Xác nhận khớp đúng giá và khối lượng đề xuất
            fill_res = self.db.record_order_fill(
                order_id=order_id,
                executed_price=order["proposed_price"],
                executed_volume=order["proposed_volume"],
                notes="Xác nhận khớp chuẩn qua nút Telegram"
            )

            confirm_msg = (
                f"🎉 <b>XÁC NHẬN KHỚP LỆNH THÀNH CÔNG!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• Mã lệnh: <code>{order_id}</code>\n"
                f"• Cổ phiếu: <b>{fill_res['ticker']}</b> ({fill_res['action']})\n"
                f"• Khớp: <code>{fill_res['executed_volume']:,} CP @ {fill_res['executed_price']:,.2f}</code>\n"
                f"• Phí CTCK (0.15%): <code>{fill_res['fee']:,.0f} VND</code>\n\n"
                f"💰 <i>Đã hạch toán vào danh mục và điều chỉnh số dư tiền mặt.</i>"
            )
            await query.edit_message_text(confirm_msg, parse_mode="HTML")

        elif action_type == "reject_order":
            # Bác bấm: [❌ TỪ CHỐI / BỎ QUA]
            with self.db.get_connection() as conn:
                conn.execute("UPDATE order_history SET status = 'CANCELLED' WHERE order_id = ?;", (order_id,))
                conn.commit()

            await query.edit_message_text(f"❌ <b>Đã hủy bỏ đề xuất lệnh:</b> <code>{order_id}</code>", parse_mode="HTML")

        elif action_type == "fill_custom_prompt":
            # Bác bấm: [✍️ BÁO KHỚP KHÁC]
            prompt_msg = (
                f"✍️ <b>BÁO KHỚP KHÁC CHO LỆNH:</b> <code>{order_id}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Bác hãy gửi tin nhắn theo cú pháp:\n"
                f"👉 <code>/fill MÃ KHỐI_LƯỢNG GIÁ</code>\n"
                f"Ví dụ: <code>/fill HPG 3000 28.1</code>"
            )
            await query.message.reply_text(prompt_msg, parse_mode="HTML")

    # ==========================================
    # NATURAL LANGUAGE TEXT PARSER (PARSER TỰ NHIÊN)
    # ==========================================
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Bóc tách tin nhắn văn bản tự nhiên:
        Ví dụ Bạn nhắn: "khớp HPG 5000 giá 28.2" hoặc "mua HPG 3000 28.1"
        """
        text = update.message.text.strip()

        # Regex tìm mẫu: [khớp/mua/bán] [MÃ] [SỐ LƯỢNG] [giá] [MỨC GIÁ]
        pattern = r"(?:khớp|khop|mua|bán|ban)?\s*([a-zA-Z]{3})\s+(\d+[\d,\.]*)\s*(?:giá|gia|@)?\s*(\d+[\d,\.]*)"
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            ticker = match.group(1).upper()
            vol_raw = match.group(2).replace(",", "").replace(".", "")
            price_raw = match.group(3).replace(",", ".")

            try:
                volume = int(vol_raw)
                price = float(price_raw)
                action = "SELL" if "bán" in text.lower() or "ban" in text.lower() else "BUY"
                strategy_book = "CORE" if re.search(r"\bcore\b", text, re.IGNORECASE) else "QUANT"

                order_id = self.db.record_retroactive_fill(
                    ticker=ticker,
                    action=action,
                    executed_price=price,
                    executed_volume=volume,
                    notes=f"Nhận diện tự nhiên: '{text}' ({strategy_book})",
                    strategy_book=strategy_book
                )

                reply = (
                    f"🤖 <b>AI ĐÃ HIỂU VÀ GHI NHẬN KHỚP LỆNH:</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• Hành động: <b>{action} {ticker}</b>\n"
                    f"• Sổ chiến lược: <code>[{strategy_book}]</code>\n"
                    f"• Khối lượng: <code>{volume:,} CP</code>\n"
                    f"• Giá thực tế: <code>{price:,.2f}</code>\n"
                    f"• Mã lệnh: <code>{order_id}</code>\n\n"
                    f"✅ Đã chốt sổ vào danh mục thành công!"
                )
                await update.message.reply_text(reply, parse_mode="HTML")
            except Exception as e:
                await update.message.reply_text(f"⚠️ Nhận diện thấy lệnh nhưng xử lý lỗi: {e}")

    # ==========================================
    # CÁC HÀM GỬI THÔNG BÁO CHỦ ĐỘNG (OUTBOUND NOTIFICATIONS)
    # ==========================================
    async def send_proposal(
        self,
        order_id: str,
        ticker: str,
        action: str,
        proposed_price: float,
        proposed_volume: int,
        stop_loss_price: float,
        target_price: float,
        bull_points: str,
        bear_points: str,
        nav_weight_pct: float,
        strategy_book: str = "QUANT"
    ):
        """Gửi Tờ trình đầu tư kèm 3 nút bấm tương tác"""
        if not self.app:
            self.build_application()

        msg = TelegramMessageFormatter.format_trade_proposal(
            order_id=order_id,
            ticker=ticker,
            action=action,
            proposed_price=proposed_price,
            proposed_volume=proposed_volume,
            stop_loss_price=stop_loss_price,
            target_price=target_price,
            bull_points=bull_points,
            bear_points=bear_points,
            nav_weight_pct=nav_weight_pct,
            strategy_book=strategy_book
        )

        keyboard = [
            [
                InlineKeyboardButton("✅ ĐÃ KHỚP CHUẨN", callback_data=f"fill_standard:{order_id}"),
                InlineKeyboardButton("✍️ KHỚP KHÁC", callback_data=f"fill_custom_prompt:{order_id}")
            ],
            [
                InlineKeyboardButton("❌ TỪ CHỐI / BỎ QUA", callback_data=f"reject_order:{order_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.app.bot.send_message(
            chat_id=self.chat_id,
            text=msg,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

def main():
    bot = FundTelegramBot()
    if not bot.token:
        print("❌ Chưa cấu hình TELEGRAM_BOT_TOKEN trong file .env!")
        print("💡 Hãy copy .env.example thành .env và điền Token từ @BotFather.")
        return
    print("🤖 Đang khởi chạy Telegram Bot của Quỹ Đầu tư AI...")
    app = bot.build_application()
    print("✅ Bot đang lắng nghe tin nhắn và nút bấm 24/7...")
    app.run_polling()

if __name__ == "__main__":
    main()

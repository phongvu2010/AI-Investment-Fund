"""
Module Định dạng Tin nhắn Telegram (Message Templates).
Tạo giao diện tin nhắn trực quan, chuyên nghiệp theo phong cách Quỹ đầu tư.
"""

from typing import Dict, List, Any
from datetime import datetime

class TelegramMessageFormatter:
    """Định dạng tin nhắn Telegram với Markdown chuẩn"""

    @staticmethod
    def format_trade_proposal(
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
    ) -> str:
        """Định dạng Tờ trình Đầu tư gửi Bạn phê duyệt kèm Badge Chiến lược Dual-Book"""
        action_emoji = "🟢 [KHUYẾN NGHỊ MUA]" if action.upper() == "BUY" else "🔴 [KHUYẾN NGHỊ BÁN]"
        book_badge = "📘 [CORE - FUNDAMENTAL]" if strategy_book.upper() == "CORE" else "⚡ [QUANT - TRADING]"
        total_val = (proposed_price * proposed_volume)
        price_unit = "k" if proposed_price < 1000.0 else "đ"
        sl_pct = "-15.0%" if strategy_book.upper() == "CORE" else "-7.0%"

        msg = (
            f"🎯 <b>{action_emoji} - {ticker.upper()}</b>\n"
            f"🏷️ <b>Sổ Chiến Lược:</b> <code>{book_badge}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Mã lệnh:</b> <code>{order_id}</code>\n"
            f"• <b>Vùng giá đề xuất:</b> <code>{proposed_price:,.2f} {price_unit}</code>\n"
            f"• <b>Khối lượng:</b> <code>{proposed_volume:,} CP</code> (~{total_val:,.0f} {price_unit})\n"
            f"• <b>Tỷ trọng danh mục:</b> <code>{nav_weight_pct:.1f}% NAV</code>\n"
            f"• <b>Cắt lỗ (Stop-loss):</b> <code>{stop_loss_price:,.2f} {price_unit}</code> ({sl_pct})\n"
            f"• <b>Mục tiêu 1 (Target):</b> <code>{target_price:,.2f} {price_unit}</code> (+15.0%)\n\n"
            f"🐂 <b>Luận điểm Phe Bò:</b>\n"
            f"<i>{bull_points}</i>\n\n"
            f"🐻 <b>Phản biện Phe Gấu (Rủi ro):</b>\n"
            f"<i>{bear_points}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 <i>Bác hãy đặt lệnh trên App CTCK. Khi nào khớp xong, hãy bấm nút xác nhận bên dưới:</i>"
        )
        return msg

    @staticmethod
    def format_nav_summary(nav_data: Dict[str, Any]) -> str:
        """Định dạng báo cáo NAV thường nhật (0 Token)"""
        total_nav = nav_data.get("total_nav", 0.0)
        cash = nav_data.get("cash_balance", 0.0)
        stock_val = nav_data.get("stock_value", 0.0)
        daily_pnl = nav_data.get("daily_pnl", 0.0)
        daily_pct = nav_data.get("daily_pnl_pct", 0.0)
        cum_pnl = nav_data.get("cumulative_pnl", 0.0)
        cum_pct = (cum_pnl / 1_000_000_000.0) * 100.0 if total_nav > 0 else 0.0

        pnl_icon = "🟢" if daily_pnl >= 0 else "🔴"
        cum_icon = "🟢" if cum_pnl >= 0 else "🔴"

        msg = (
            f"🏛️ <b>BÁO CÁO TÀI SẢN QUỸ (NAV SUMMARY)</b>\n"
            f"📅 Ngày chốt sổ: <code>{nav_data.get('trade_date', 'Hôm nay')}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>Tổng tài sản (NAV):</b> <code>{total_nav:,.0f} VND</code>\n"
            f"💵 <b>Tiền mặt khả dụng:</b> <code>{cash:,.0f} VND</code> ({cash/total_nav*100:.1f}%)\n"
            f"📈 <b>Giá trị Cổ phiếu:</b> <code>{stock_val:,.0f} VND</code> ({stock_val/total_nav*100:.1f}%)\n\n"
            f"📊 <b>Biến động trong ngày:</b>\n"
            f"{pnl_icon} <code>{daily_pnl:+,.0f} VND ({daily_pct:+.2f}%)</code>\n\n"
            f"🏆 <b>Lợi nhuận lũy kế (All-Time):</b>\n"
            f"{cum_icon} <code>{cum_pnl:+,.0f} VND ({cum_pct:+.2f}%)</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Gõ <code>/portfolio</code> để xem chi tiết từng mã đang giữ."
        )
        return msg

    @staticmethod
    def format_portfolio_table(portfolio: List[Dict[str, Any]]) -> str:
        """Định dạng danh mục cổ phiếu đang nắm giữ"""
        if not portfolio:
            return "📭 <b>Danh mục hiện tại đang trống (100% Tiền mặt).</b>\nQuỹ đang rình mồi chờ cơ hội mới!"

        msg = (
            f"📊 <b>DANH MỤC CỔ PHIẾU ĐANG NẮM GIỮ ({len(portfolio)} mã)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        total_unreal = 0.0
        for item in portfolio:
            t = item["ticker"]
            q = item["quantity"]
            avg_p = item["avg_buy_price"]
            cur_p = item.get("current_price", avg_p)
            unreal_pnl = item.get("unrealized_pnl", 0.0)
            unreal_pct = item.get("unrealized_pnl_pct", 0.0)
            total_unreal += unreal_pnl

            icon = "🟢" if unreal_pnl >= 0 else "🔴"
            s_book = item.get("strategy_book", "QUANT")
            book_tag = " [CORE]" if s_book == "CORE" else " [QUANT]"
            msg += (
                f"🔹 <b>{t}</b><code>{book_tag}</code> | {icon} <code>{unreal_pct:+.2f}%</code>\n"
                f"   • Khối lượng: <code>{q:,} CP</code>\n"
                f"   • Giá vốn: <code>{avg_p:,.2f}</code> ➔ Thị giá: <code>{cur_p:,.2f}</code>\n"
                f"   • Lãi/Lỗ: <code>{unreal_pnl:+,.0f} VND</code>\n\n"
            )

        msg += (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 <b>Tổng Lợi nhuận tạm tính:</b> <code>{total_unreal:+,.0f} VND</code>"
        )
        return msg

    @staticmethod
    def format_evening_check(pending_orders: List[Dict[str, Any]]) -> str:
        """Định dạng tin nhắn đối soát buổi tối lúc 20h00"""
        msg = (
            f"🔔 <b>[ĐỐI SOÁT GIAO DỊCH CUỐI NGÀY]</b>\n"
            f"Hôm nay Quỹ có {len(pending_orders)} lệnh chờ xác nhận khớp.\n"
            f"Bác đã khớp được trên app chưa để em chốt sổ NAV ạ?\n\n"
        )
        for ord in pending_orders:
            msg += (
                f"• <b>{ord['ticker']}</b> ({ord['action']}): "
                f"<code>{ord['proposed_volume']:,} CP @ {ord['proposed_price']:,.2f}</code>\n"
                f"  Mã lệnh: <code>{ord['order_id']}</code>\n"
            )
        msg += "\n👉 Bác hãy bấm nút bên dưới hoặc gõ <code>/fill MÃ SỐ_LƯỢNG GIÁ</code> để nhập bù."
        return msg

"""
Harness Context Manager (State & Memory Injection).
Tự động nén và nạp ngữ cảnh chuẩn (NAV, sức mua khả dụng, tỷ trọng sổ CORE/QUANT,
trạng thái thị trường từ ParquetMarketDataManager, và bài học thất bại từ .agent/journals/)
vào prompt của các AI Agents trước mỗi phiên họp Ủy ban Đầu tư.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import json

from config import settings
from database.db_manager import DatabaseManager
from tools.parquet_manager import ParquetMarketDataManager


class HarnessContextManager:
    """Quản trị Ngữ cảnh Vận hành & Bộ nhớ Thể chế cho AI Agents"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager()
        self.parquet_mgr = ParquetMarketDataManager()
        self.journals_dir = settings.BASE_DIR / ".agent" / "journals"

    def get_recent_journal_lessons(self, limit: int = 3) -> List[Dict[str, str]]:
        """Đọc và trích xuất các bài học thất bại gần nhất từ .agent/journals/"""
        if not self.journals_dir.exists():
            return []

        journal_files = sorted(
            [f for f in self.journals_dir.glob("*.md") if f.name != ".gitkeep"],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

        lessons = []
        for f in journal_files[:limit]:
            try:
                content = f.read_text(encoding="utf-8")
                lessons.append({
                    "filename": f.name,
                    "title": f.stem,
                    "excerpt": content[:600]
                })
            except Exception:
                continue

        return lessons

    def get_committee_context(self, ticker: str, strategy_book: str = "QUANT") -> Dict[str, Any]:
        """
        Nén và tổng hợp toàn diện ngữ cảnh thời gian thực của Quỹ:
        - NAV hiện tại, Tiền mặt khả dụng, Biến động ngày & tuần
        - Tỷ trọng phân bổ Dual-Book (CORE 70% vs QUANT 30%)
        - Vị thế hiện có của mã đối tượng
        - Trạng thái khí tượng & độ rộng thị trường (Market Regime)
        - Bộ nhớ thể chế (Bài học thất bại gần nhất)
        """
        t = ticker.upper()
        book = strategy_book.upper()

        nav_info = self.db.get_latest_nav() or {}
        total_nav = float(nav_info.get("total_nav", settings.INITIAL_CAPITAL))
        cash_balance = self.db.get_current_cash()
        stock_value = float(nav_info.get("stock_value", 0.0))
        weekly_dd = abs(float(nav_info.get("weekly_drawdown_pct", 0.0)))
        daily_pnl_pct = float(nav_info.get("daily_pnl_pct", 0.0))

        # Phân bổ vị thế theo sổ
        portfolio = self.db.get_portfolio()
        core_val = sum(p["market_value"] for p in portfolio if p.get("strategy_book", "QUANT") == "CORE")
        quant_val = sum(p["market_value"] for p in portfolio if p.get("strategy_book", "QUANT") == "QUANT")

        core_pct = core_val / max(1.0, total_nav)
        quant_pct = quant_val / max(1.0, total_nav)
        cash_pct = cash_balance / max(1.0, total_nav)

        # Vị thế hiện tại của ticker
        ticker_positions = [p for p in portfolio if p["ticker"] == t]
        curr_vol = sum(p["quantity"] for p in ticker_positions)
        curr_val = sum(p["market_value"] for p in ticker_positions)
        curr_weight = curr_val / max(1.0, total_nav)

        # Trạng thái thị trường
        try:
            market_regime = self.parquet_mgr.get_market_regime()
        except Exception:
            market_regime = {"regime": "SIDEWAY", "breadth_ma20_pct": 50.0, "freeze_quant": False}

        # Bài học thất bại từ journals
        recent_lessons = self.get_recent_journal_lessons(limit=2)

        return {
            "ticker": t,
            "strategy_book": book,
            "fund_state": {
                "total_nav": total_nav,
                "cash_balance": cash_balance,
                "stock_value": stock_value,
                "cash_weight_pct": round(cash_pct * 100, 2),
                "weekly_drawdown_pct": round(weekly_dd * 100, 2),
                "daily_pnl_pct": round(daily_pnl_pct * 100, 2),
                "core_weight_pct": round(core_pct * 100, 2),
                "quant_weight_pct": round(quant_pct * 100, 2),
                "core_max_pct": round(settings.CORE_MAX_ALLOCATION_PCT * 100, 2),
                "quant_max_pct": round(settings.QUANT_MAX_ALLOCATION_PCT * 100, 2),
            },
            "position_state": {
                "ticker": t,
                "current_holding_vol": curr_vol,
                "current_holding_value": curr_val,
                "current_weight_pct": round(curr_weight * 100, 2),
                "max_position_pct": round(
                    (settings.CORE_MAX_POSITION_PCT if book == "CORE" else settings.QUANT_MAX_POSITION_PCT) * 100,
                    2
                )
            },
            "market_regime": market_regime,
            "recent_lessons": recent_lessons
        }

    def format_prompt_context(self, ticker: str, strategy_book: str = "QUANT") -> str:
        """Định dạng ngữ cảnh thành văn bản chuẩn mực để chèn vào System Prompt của Agent"""
        ctx = self.get_committee_context(ticker, strategy_book)
        fs = ctx["fund_state"]
        ps = ctx["position_state"]
        mr = ctx["market_regime"]
        lessons = ctx["recent_lessons"]

        lines = [
            "=================== [HARNESS CONTEXT INJECTION] ===================",
            f"1. TRẠNG THÁI QUỸ (NAV: {fs['total_nav']:,.0f} VND):",
            f"   - Tiền mặt: {fs['cash_balance']:,.0f} VND ({fs['cash_weight_pct']}%)",
            f"   - Phân bổ sổ: CORE {fs['core_weight_pct']}% / Max {fs['core_max_pct']}% | QUANT {fs['quant_weight_pct']}% / Max {fs['quant_max_pct']}%",
            f"   - Biến động tuần (Drawdown): -{fs['weekly_drawdown_pct']}% (Ngưỡng Circuit Breaker: 5.0%)",
            "",
            f"2. VỊ THẾ HIỆN TẠI [{ctx['ticker']}]:",
            f"   - Khối lượng đang giữ: {ps['current_holding_vol']:,} CP (Giá trị: {ps['current_holding_value']:,.0f} VND)",
            f"   - Tỷ trọng hiện có: {ps['current_weight_pct']}% / Trần tối đa {ps['max_position_pct']}%",
            "",
            f"3. KHÍ TƯỢNG THỊ TRƯỜNG: [{mr.get('regime', 'SIDEWAY')}]",
            f"   - Độ rộng MA20: {mr.get('breadth_ma20_pct', 50.0)}% | Đóng băng QUANT: {mr.get('freeze_quant', False)}",
        ]

        if lessons:
            lines.append("")
            lines.append("4. BÀI HỌC THẤT BẠI CẦN TRÁNH (POST-MORTEM LESSONS):")
            for idx, l in enumerate(lessons, 1):
                first_lines = l["excerpt"].split("\n")[:4]
                summary = " ".join([x.strip() for x in first_lines if x.strip()])
                lines.append(f"   [{idx}] {l['title']}: {summary[:160]}...")

        lines.append("===================================================================")
        return "\n".join(lines)

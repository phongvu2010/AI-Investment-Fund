"""
Harness Guardrail Middleware (Permissions & Hard Veto).
Bọc quanh mọi hành động tạo đề xuất lệnh (db.create_proposed_order) và sinh chiến lược.
Kết hợp JevDecisionEngine.score_execution_risk() với các Hard Rules trong config/settings.py:
- CORE_MAX_POSITION_PCT = 0.25 (25% NAV)
- QUANT_MAX_POSITION_PCT = 0.15 (15% NAV)
- MAX_WEEKLY_DRAWDOWN_PCT = 0.05 (5.0% Circuit Breaker)
- Kiểm tra quy chế khả dụng T+2.5
- Kiểm tra kẹt sàn / Trắng bên mua (Floor-lock)
Nếu vi phạm bất kỳ quy tắc nào HOẶC risk_score > 0.70: Chặn cứng hành động (VETO) và ghi log audit.
"""

from datetime import datetime, date
from typing import Dict, Any, Optional, Tuple
import sqlite3
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings
from database.db_manager import DatabaseManager
from tools.jev_decision_engine import JevDecisionEngine, Score


class GuardrailVetoException(ValueError):
    """Ngoại lệ ném ra khi vi phạm Hard Rules hoặc rủi ro thực thi vượt ngưỡng"""
    pass


class GuardrailMiddleware:
    """Bộ lọc Kiểm soát Quyền hạn & Phủ quyết Cứng (Hard Veto)"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager()
        self.jev = JevDecisionEngine()
        self._ensure_audit_table()

    def _ensure_audit_table(self):
        """Khởi tạo bảng guardrail_audit_log trong SQLite nếu chưa có"""
        with self.db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS guardrail_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT,
                    ticker TEXT NOT NULL,
                    strategy_book TEXT NOT NULL,
                    action TEXT NOT NULL,
                    proposed_price REAL,
                    proposed_volume INTEGER,
                    risk_score REAL NOT NULL,
                    verdict TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    audit_metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

    def log_audit(
        self,
        ticker: str,
        strategy_book: str,
        action: str,
        proposed_price: float,
        proposed_volume: int,
        risk_score: float,
        verdict: str,
        reason: str,
        order_id: Optional[str] = None,
        audit_metadata: Optional[Dict[str, Any]] = None
    ):
        """Ghi vết bảo mật mọi phán quyết kiểm duyệt vào SQLite"""
        import json
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO guardrail_audit_log (
                    order_id, ticker, strategy_book, action, proposed_price,
                    proposed_volume, risk_score, verdict, reason, audit_metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                order_id,
                ticker.upper(),
                strategy_book.upper(),
                action.upper(),
                proposed_price,
                proposed_volume,
                round(risk_score, 4),
                verdict,
                reason,
                json.dumps(audit_metadata or {}, ensure_ascii=False),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            conn.commit()

    def validate_order(
        self,
        ticker: str,
        action: str,
        proposed_price: float,
        proposed_volume: int,
        strategy_book: str = "QUANT",
        account: str = "0001716319",
        trade_date: Optional[str] = None
    ) -> Tuple[bool, str, Score]:
        """
        Kiểm tra toàn diện trước khi phát lệnh:
        1. Cổ phiếu treo sàn / đình chỉ (FLC = 0 VND)
        2. Quy chế T+2.5 nếu BÁN
        3. Circuit breaker sụt giảm tuần (Weekly MDD > 5%)
        4. Giới hạn tỷ trọng vị thế theo sổ (CORE 25%, QUANT 15%)
        5. Kẹt sàn / Trắng bên mua
        6. Chấm điểm rủi ro thực thi Jev AI (risk_score > 0.70)
        """
        t = ticker.upper()
        act = action.upper()
        book = strategy_book.upper()
        t_date = trade_date or date.today().strftime("%Y-%m-%d")

        norm_price = proposed_price * 1000.0 if proposed_price < 1000.0 else proposed_price

        # 1. Kiểm tra cổ phiếu bị đình chỉ / treo sàn
        if t in {"FLC"}:
            reason = f"CRO VETO [SUSPENDED ASSET]: Cổ phiếu {t} bị đình chỉ giao dịch hoặc định giá 0 VND."
            risk = Score(value=1.0, confidence=1.0, latency_ms=0.1, reasoning=reason)
            return False, reason, risk

        # 2. Kiểm tra quy chế T+2.5 khi BÁN
        avail_qty = 0
        if act == "SELL":
            avail_info = self.db.calculate_available_shares(
                ticker=t, account=account, strategy_book=book, as_of_date=t_date
            )
            avail_qty = avail_info.get("available_quantity", 0)
            if proposed_volume > avail_qty:
                reason = (
                    f"CRO VETO [T+2.5 SETTLEMENT]: Không thể tạo lệnh BÁN {proposed_volume:,} CP {t}. "
                    f"Số lượng khả dụng chỉ có {avail_qty:,} CP. Đang chờ về T+2.5: {avail_info.get('pending_settlement_quantity', 0):,} CP."
                )
                risk = Score(value=0.95, confidence=0.99, latency_ms=0.5, reasoning=reason)
                return False, reason, risk

        # Lấy trạng thái tài khoản & danh mục
        nav_info = self.db.get_latest_nav() or {}
        total_nav = float(nav_info.get("total_nav", settings.INITIAL_CAPITAL))
        weekly_dd = abs(float(nav_info.get("weekly_drawdown_pct", 0.0)))

        # 3. Kiểm tra Circuit Breaker sụt giảm tuần
        if act == "BUY" and weekly_dd > settings.MAX_WEEKLY_DRAWDOWN_PCT:
            reason = (
                f"CRO VETO [CIRCUIT BREAKER]: Mức sụt giảm tuần ({weekly_dd*100:.2f}%) "
                f"vượt ngưỡng kỷ luật quỹ ({settings.MAX_WEEKLY_DRAWDOWN_PCT*100:.1f}%). Đóng băng mở mới vị thế."
            )
            risk = Score(value=0.90, confidence=0.98, latency_ms=0.5, reasoning=reason)
            return False, reason, risk

        # 4. Kiểm tra giới hạn tỷ trọng vị thế
        portfolio = self.db.get_portfolio()
        curr_vol = sum(p["quantity"] for p in portfolio if p["ticker"] == t and p.get("strategy_book", "QUANT") == book)
        curr_val = curr_vol * norm_price
        max_pct = settings.CORE_MAX_POSITION_PCT if book == "CORE" else settings.QUANT_MAX_POSITION_PCT
        max_capital = total_nav * max_pct

        if act == "BUY":
            new_val = curr_val + (proposed_volume * norm_price)
            if new_val > max_capital * 1.001:  # Sai số làm tròn nhỏ
                reason = (
                    f"CRO VETO [CONCENTRATION LIMIT]: Giá trị sau giải ngân ({new_val:,.0f} VND) "
                    f"vượt hạn mức tối đa của sổ {book} ({max_pct*100:.0f}% NAV = {max_capital:,.0f} VND)."
                )
                risk = Score(value=0.85, confidence=0.95, latency_ms=0.5, reasoning=reason)
                return False, reason, risk

        # 5. Chấm điểm rủi ro thực thi Jev AI System 1
        portfolio_state = {
            "total_nav": total_nav,
            "current_position_value": curr_val,
            "strategy_book": book,
            "weekly_drawdown_pct": weekly_dd,
            "available_quantity": avail_qty if act == "SELL" else proposed_volume
        }

        risk_score = self.jev.score_execution_risk(
            ticker=t,
            action=act,
            proposed_vol=proposed_volume,
            portfolio_state=portfolio_state,
            proposed_price=proposed_price
        )

        if risk_score.value > 0.70:
            reason = f"CRO VETO [EXECUTION RISK > 0.70]: Điểm rủi ro thực thi Jev AI = {risk_score.value:.2f}. {risk_score.reasoning}"
            return False, reason, risk_score

        return True, "APPROVED: Lệnh thỏa mãn 100% Guardrails & Hard Rules của Quỹ.", risk_score

    def create_verified_proposed_order(
        self,
        ticker: str,
        action: str,
        proposed_price: float,
        proposed_volume: int,
        order_type: str = "LO",
        memo_id: Optional[str] = None,
        notes: Optional[str] = None,
        trade_date: Optional[str] = None,
        account: str = "0001716319",
        strategy_book: str = "QUANT"
    ) -> str:
        """
        Hàm bọc quanh db.create_proposed_order.
        Tự động chạy qua GuardrailMiddleware:
        - Nếu vi phạm: ném GuardrailVetoException và ghi log audit.
        - Nếu hợp lệ: gọi db.create_proposed_order và ghi log audit thành công.
        """
        is_valid, reason, risk_score = self.validate_order(
            ticker=ticker,
            action=action,
            proposed_price=proposed_price,
            proposed_volume=proposed_volume,
            strategy_book=strategy_book,
            account=account,
            trade_date=trade_date
        )

        if not is_valid:
            self.log_audit(
                ticker=ticker,
                strategy_book=strategy_book,
                action=action,
                proposed_price=proposed_price,
                proposed_volume=proposed_volume,
                risk_score=risk_score.value,
                verdict="VETO",
                reason=reason,
                order_id=None,
                audit_metadata=risk_score.metadata
            )
            raise GuardrailVetoException(reason)

        # Lệnh hợp lệ, tiến hành tạo lệnh
        order_id = self.db.create_proposed_order(
            ticker=ticker,
            action=action,
            proposed_price=proposed_price,
            proposed_volume=proposed_volume,
            order_type=order_type,
            memo_id=memo_id,
            notes=notes,
            trade_date=trade_date,
            account=account,
            strategy_book=strategy_book
        )

        self.log_audit(
            ticker=ticker,
            strategy_book=strategy_book,
            action=action,
            proposed_price=proposed_price,
            proposed_volume=proposed_volume,
            risk_score=risk_score.value,
            verdict="APPROVED",
            reason=reason,
            order_id=order_id,
            audit_metadata=risk_score.metadata
        )

        return order_id

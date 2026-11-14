"""
Bộ Kiểm Thử Tự Động Kiến Trúc Hybrid System 1 + System 2 (Jev AI & Harness).
Kiểm chứng toàn bộ các ràng buộc kiến trúc:
1. JevDecisionEngine: trả về đúng các primitives Noul, Choice, Score kèm confidence, probabilities và độ trễ < 500ms.
2. Harness Guardrail Middleware: Chặn cứng vi phạm trần NAV, vi phạm T+2.5, kẹt sàn và rủi ro thực thi > 0.70.
3. Harness Verification Loop: Tự động phát hiện Overfitting/REJECTED và kích hoạt vòng lặp tối ưu hóa + Post-Mortem.
4. Tích hợp System 1 + System 2: LLM Gate (confidence >= 0.75) và API Telemetry.
"""

import sys
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings
from database.db_manager import DatabaseManager
from tools.jev_decision_engine import JevDecisionEngine, Noul, Choice, Score
from harness.context_manager import HarnessContextManager
from harness.guardrail_middleware import GuardrailMiddleware, GuardrailVetoException
from harness.verification_loop import HarnessVerificationLoop
from tools.investment_debate_engine import InvestmentDebateEngine
from backtest.strategy_template import BaseFundStrategy, indicator_sma, indicator_volume_sma
from dashboard.api import app


# ====================================================================
# CHIẾN LƯỢC MẪU CHO TEST VERIFICATION LOOP
# ====================================================================
class OverfittedTestStrategy(BaseFundStrategy):
    """Chiến lược cố tình tạo điều kiện vào lệnh siêu khắt khe để bị CRO từ chối"""
    def init(self):
        self.ma20_close = self.I(indicator_sma, length=20, ticker="HPG")
        self.ma20_vol = self.I(indicator_volume_sma, length=20, ticker="HPG")

    def next(self):
        close = self.get_close("HPG")
        vol = self.get_volume("HPG")
        ma_c = self.ma20_close[-1]
        ma_v = self.ma20_vol[-1]

        if ma_c is None or ma_v is None:
            return

        # Điều kiện vol quá cao (> 5.0x) dẫn đến mẫu lệnh không đủ
        if not self.is_holding("HPG"):
            if close > ma_c * 1.05 and vol > ma_v * 5.0:
                self.buy("HPG", size=100)
        elif self.is_holding("HPG") and close < ma_c:
            self.sell("HPG")


class TestJevDecisionEngine:
    """Kiểm thử Cỗ máy Phản xạ Jev AI System 1"""

    def setup_method(self):
        self.jev = JevDecisionEngine()

    def test_noul_triage_structure_and_latency(self):
        """Xác nhận Noul trả về đúng cấu trúc nhị phân, confidence và latency < 500ms"""
        # 1. Sự kiện thông thường (Nhiễu thị trường)
        res_normal = self.jev.triage_market_event("HPG")
        assert isinstance(res_normal, Noul)
        assert isinstance(res_normal.value, bool)
        assert res_normal.value is False
        assert 0.0 <= res_normal.confidence <= 1.0
        assert "True" in res_normal.probabilities
        assert "False" in res_normal.probabilities
        assert res_normal.latency_ms < 500.0

        # 2. Sự kiện trọng yếu tiêu cực (Tin tức bắt bớ, gian lận)
        res_critical = self.jev.triage_market_event(
            "HPG",
            news_text="Chủ tịch bị khởi tố và bắt tạm giam vì nghi vấn gian lận BCTC",
            intraday_bar={"pct_change": 6.8, "is_floor": True}
        )
        assert res_critical.value is True
        assert res_critical.confidence >= 0.70
        assert "True" in res_critical.probabilities
        assert res_critical.probabilities["True"] >= 0.70
        assert res_critical.latency_ms < 500.0

        # 3. Mã bị đình chỉ (FLC)
        res_flc = self.jev.triage_market_event("FLC")
        assert res_flc.value is True
        assert res_flc.confidence >= 0.90

    def test_choice_route_structure_and_latency(self):
        """Xác nhận Choice trả về đúng định tuyến Enum (CORE/QUANT/IGNORE) và latency < 500ms"""
        # 1. Cổ phiếu bluechip nền tảng tốt -> CORE
        res_core = self.jev.route_strategy_book(
            "HPG",
            fa_summary={"fa_score": 85.0, "has_critical_flags": False, "red_flags": []},
            ml_score=0.50
        )
        assert isinstance(res_core, Choice)
        assert res_core.value in ["CORE", "QUANT", "IGNORE"]
        assert res_core.value == "CORE"
        assert 0.0 <= res_core.confidence <= 1.0
        assert "CORE" in res_core.probabilities
        assert "QUANT" in res_core.probabilities
        assert "IGNORE" in res_core.probabilities
        assert res_core.latency_ms < 500.0

        # 2. Cổ phiếu cờ đỏ nghiêm trọng -> IGNORE
        res_ignore = self.jev.route_strategy_book(
            "TEST",
            fa_summary={"fa_score": 30.0, "has_critical_flags": True, "red_flags": ["Ý kiến ngoại trừ"]},
            ml_score=0.20
        )
        assert res_ignore.value == "IGNORE"

        # 3. Mã FLC -> Bắt buộc IGNORE
        res_flc = self.jev.route_strategy_book("FLC")
        assert res_flc.value == "IGNORE"

    def test_score_execution_risk_structure_and_latency(self):
        """Xác nhận Score trả về điểm số rủi ro liên tục [0.0, 1.0] và latency < 500ms"""
        # 1. Lệnh an toàn bình thường
        res_safe = self.jev.score_execution_risk(
            ticker="HPG",
            action="BUY",
            proposed_vol=1000,
            liq_metrics={"is_liquid": True, "is_currently_floor_locked": False, "is_near_floor": False, "adv": 2000000}
        )
        assert isinstance(res_safe, Score)
        assert 0.0 <= res_safe.value <= 1.0
        assert res_safe.value <= 0.40
        assert res_safe.latency_ms < 500.0

        # 2. Lệnh rủi ro cực đoan (Kẹt sàn / Trắng bên mua)
        res_floor = self.jev.score_execution_risk(
            ticker="HPG",
            action="BUY",
            proposed_vol=1000,
            liq_metrics={"is_currently_floor_locked": True, "is_liquid": True}
        )
        assert res_floor.value > 0.70
        assert "floor_locked" in res_floor.metadata.get("factors", {})


class TestHarnessGuardrails:
    """Kiểm thử Hệ thống Rào Chắn Kiểm Soát & Phủ Quyết Cứng (Guardrail Middleware)"""

    def setup_method(self):
        self.test_db_path = settings.DATABASE_DIR / "test_guardrail_vault.db"
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        self.db = DatabaseManager(db_path=self.test_db_path)
        self.guardrail = GuardrailMiddleware(db_manager=self.db)

    def teardown_method(self):
        if self.test_db_path.exists():
            try:
                self.test_db_path.unlink()
            except Exception:
                pass

    def test_guardrail_blocks_nav_limit_breach(self):
        """Guardrail chặn lệnh mua vượt quá trần phân bổ NAV (QUANT tối đa 15%)"""
        # NAV khởi điểm 1 tỷ VND. Hạn mức sổ QUANT = 150 triệu VND (15%).
        # Mua 10.000 CP giá 28.000 VND = 280 triệu VND (> 150 triệu).
        with pytest.raises(GuardrailVetoException) as exc_info:
            self.guardrail.create_verified_proposed_order(
                ticker="HPG",
                action="BUY",
                proposed_price=28.0,
                proposed_volume=10000,
                strategy_book="QUANT"
            )
        assert "CONCENTRATION LIMIT" in str(exc_info.value) or "vượt hạn mức" in str(exc_info.value)

        # Kiểm tra nhật ký kiểm duyệt SQLite (Audit Trail)
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM guardrail_audit_log WHERE ticker = 'HPG' ORDER BY id DESC LIMIT 1;").fetchone()
            assert row is not None
            assert row["verdict"] == "VETO"

    def test_guardrail_blocks_t25_violation(self):
        """Guardrail chặn lệnh bán khi không có đủ cổ phiếu khả dụng T+2.5"""
        with pytest.raises(GuardrailVetoException) as exc_info:
            self.guardrail.create_verified_proposed_order(
                ticker="HPG",
                action="SELL",
                proposed_price=28.0,
                proposed_volume=5000,
                strategy_book="QUANT"
            )
        assert "T+2.5 SETTLEMENT" in str(exc_info.value)

    def test_guardrail_blocks_suspended_stock(self):
        """Guardrail chặn giao dịch cổ phiếu đình chỉ (FLC = 0 VND)"""
        with pytest.raises(GuardrailVetoException) as exc_info:
            self.guardrail.create_verified_proposed_order(
                ticker="FLC",
                action="BUY",
                proposed_price=10.0,
                proposed_volume=1000,
                strategy_book="QUANT"
            )
        assert "SUSPENDED ASSET" in str(exc_info.value)

    def test_guardrail_allows_compliant_order(self):
        """Guardrail phê duyệt lệnh hợp lệ trong hạn mức an toàn"""
        # Mua 1.000 HPG @ 28.0 = 28 triệu VND (< 150 triệu)
        order_id = self.guardrail.create_verified_proposed_order(
            ticker="HPG",
            action="BUY",
            proposed_price=28.0,
            proposed_volume=1000,
            strategy_book="QUANT"
        )
        assert order_id is not None
        assert order_id.startswith("ORD-")

        # Kiểm tra audit log
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM guardrail_audit_log WHERE order_id = ?;", (order_id,)).fetchone()
            assert row is not None
            assert row["verdict"] == "APPROVED"


class TestHarnessVerificationLoop:
    """Kiểm thử Vòng Lặp Kiểm Định & Tự Khắc Phục (Code-Backed Self-Correction)"""

    def test_verification_loop_detects_failure_and_triggers_healing(self):
        """Xác nhận Harness phát hiện chiến lược REJECTED và kích hoạt vòng lặp tối ưu + Post-Mortem"""
        loop = HarnessVerificationLoop()

        result = loop.deploy_verify_and_heal(
            strategy_class=OverfittedTestStrategy,
            strategy_id="test-overfit",
            strategy_title="Test Overfitted Strategy",
            tickers="HPG",
            description="Chiến lược kiểm thử bẫy Overfitting",
            entry_rules="Mua khi nổ vol 5x",
            exit_rules="Bán khi thủng MA20",
            days=1250,
            max_heal_loops=2
        )

        assert "verification_loop" in result
        v_loop = result["verification_loop"]
        assert v_loop["total_iterations"] >= 2
        assert len(v_loop["heal_history"]) >= 1

        # Xác nhận có biên bản Post-Mortem được lưu trong .agent/journals/
        journals_dir = settings.BASE_DIR / ".agent" / "journals"
        post_mortems = list(journals_dir.glob("post_mortem_test-overfit_*.md"))
        assert len(post_mortems) >= 1
        content = post_mortems[0].read_text(encoding="utf-8")
        assert "NHẬT KÝ KHÁM NGHIỆM CHIẾN LƯỢC" in content
        assert "BÀI HỌC THỂ CHẾ" in content


class TestHarnessSystem1System2Integration:
    """Kiểm thử Tích hợp Giữa Jev System 1 và System 2 LLM/API"""

    def test_investment_debate_llm_gate(self):
        """Xác nhận System 2 LLM chỉ được kích hoạt khi confidence >= 0.75 và qua sơ lọc"""
        debate_engine = InvestmentDebateEngine()

        # Giả lập tình huống Jev confidence thấp (< 0.75) hoặc bị loại
        res = debate_engine.generate_debate(
            ticker="HPG",
            strategy_book="CORE",
            market_regime_info={"regime": "SIDEWAY"},
            fa_res={"fa_score": 75.0, "rating": "GOOD", "summary": "Tốt", "red_flags": []},
            ml_score=0.55,
            latest_close=28.5,
            support_price=26.5,
            resistance_price=32.0,
            jev_confidence=0.60,  # Dưới 0.75
            passes_filter=True
        )
        # Bắt buộc fallback về 0-Token Multi-Factor Analytical Debate
        assert "MULTI_FACTOR" in res["engine"]
        assert "bull_arguments" in res
        assert "bear_arguments" in res

    def test_harness_context_manager_injection(self):
        """Xác nhận ContextManager nạp đầy đủ thông tin vào Prompt"""
        ctx_mgr = HarnessContextManager()
        prompt_txt = ctx_mgr.format_prompt_context("HPG", "CORE")
        assert "HARNESS CONTEXT INJECTION" in prompt_txt
        assert "TRẠNG THÁI QUỸ" in prompt_txt
        assert "KHÍ TƯỢNG THỊ TRƯỜNG" in prompt_txt

    def test_fast_triage_api_endpoint(self):
        """Xác nhận API endpoint /api/jev/triage/{ticker} phản hồi dưới 500ms"""
        client = TestClient(app)
        res = client.get("/api/jev/triage/HPG")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SUCCESS"
        assert data["ticker"] == "HPG"
        assert data["latency_ms"] < 500.0
        assert "triage" in data
        assert "route" in data
        assert "risk_score" in data

    def test_guardrails_audit_api_endpoint(self):
        """Xác nhận API endpoint /api/guardrails/audit trả về danh sách audit log"""
        client = TestClient(app)
        res = client.get("/api/guardrails/audit")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SUCCESS"
        assert "logs" in data

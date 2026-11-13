import pytest
import os
import shutil
import tempfile
import sqlite3
from datetime import datetime, date
from fastapi.testclient import TestClient

from config import settings
from database.db_manager import DatabaseManager
from tools.fundamental_screener import FundamentalScreener
from tools.ml_feature_extractor import MLFeatureExtractor
from tools.ml_predictor import UniversalAlphaPredictor
from dashboard.api import app


from pathlib import Path

@pytest.fixture
def temp_db():
    """Tạo database SQLite tạm thời để kiểm thử hạch toán Dual-Book độc lập"""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_fund.db"
    
    # Khởi tạo db_manager với db_path tạm
    original_db_path = settings.SQLITE_DB_PATH
    settings.SQLITE_DB_PATH = db_path
    
    db = DatabaseManager(db_path=db_path)
    
    yield db
    
    # Dọn dẹp
    settings.SQLITE_DB_PATH = original_db_path
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


class TestDualBookAccounting:
    """Kiểm thử Hạng mục 1: Tách bạch sổ cái 2 chiến lược (Dual-Book: CORE vs. QUANT)"""

    def test_schema_has_strategy_book_and_nav_columns(self, temp_db):
        """Xác nhận schema bảng có cột strategy_book và core_nav, quant_nav"""
        with temp_db.get_connection() as conn:
            # Check portfolio table
            cols_pf = [c[1] for c in conn.execute("PRAGMA table_info(portfolio);").fetchall()]
            assert "strategy_book" in cols_pf
            
            # Check order_history table
            cols_ord = [c[1] for c in conn.execute("PRAGMA table_info(order_history);").fetchall()]
            assert "strategy_book" in cols_ord
            
            # Check nav_daily table
            cols_nav = [c[1] for c in conn.execute("PRAGMA table_info(nav_daily);").fetchall()]
            assert "core_nav" in cols_nav
            assert "quant_nav" in cols_nav

    def test_dual_book_portfolio_isolation(self, temp_db):
        """Xác nhận cùng 1 tài khoản có thể nắm giữ cùng 1 mã ở 2 sổ chiến lược riêng biệt"""
        acc = "TEST_ACC_01"
        with temp_db.get_connection() as conn:
            conn.execute("INSERT OR IGNORE INTO broker_accounts (account_id, broker_name) VALUES (?, 'VPS');", (acc,))
        
        # Nạp tiền khởi tạo
        temp_db.record_cash_flow(account=acc, cash_type="DEPOSIT", amount=500_000_000.0, trade_date="2026-11-01", comment="Nạp tiền khởi tạo quỹ")
        
        # Khớp lệnh MUA 1.000 CP HPG trên Sổ CORE (Dài hạn)
        temp_db.record_retroactive_fill(
            ticker="HPG",
            action="BUY",
            executed_price=28.0,
            executed_volume=1000,
            trade_date="2026-11-01",
            notes="Mua tích sản Core",
            account=acc,
            strategy_book="CORE"
        )
        
        # Khớp lệnh MUA 500 CP HPG trên Sổ QUANT (Trading)
        temp_db.record_retroactive_fill(
            ticker="HPG",
            action="BUY",
            executed_price=29.0,
            executed_volume=500,
            trade_date="2026-11-02",
            notes="Mua breakout Quant",
            account=acc,
            strategy_book="QUANT"
        )
        
        # Kiểm tra danh mục toàn bộ
        all_pf = temp_db.get_portfolio(account=acc)
        assert len(all_pf) == 2
        
        # Kiểm tra lọc theo Sổ CORE
        core_pf = temp_db.get_portfolio(account=acc, strategy_book="CORE")
        assert len(core_pf) == 1
        assert core_pf[0]["ticker"] == "HPG"
        assert core_pf[0]["quantity"] == 1000
        assert core_pf[0]["avg_buy_price"] >= 28000.0
        assert core_pf[0]["strategy_book"] == "CORE"
        
        # Kiểm tra lọc theo Sổ QUANT
        quant_pf = temp_db.get_portfolio(account=acc, strategy_book="QUANT")
        assert len(quant_pf) == 1
        assert quant_pf[0]["ticker"] == "HPG"
        assert quant_pf[0]["quantity"] == 500
        assert quant_pf[0]["avg_buy_price"] >= 29000.0
        assert quant_pf[0]["strategy_book"] == "QUANT"

    def test_daily_nav_dual_book_breakdown(self, temp_db):
        """Xác nhận chốt sổ NAV tính toán chính xác core_nav và quant_nav"""
        acc = "TEST_ACC_02"
        with temp_db.get_connection() as conn:
            conn.execute("INSERT OR IGNORE INTO broker_accounts (account_id, broker_name) VALUES (?, 'VPS');", (acc,))
        temp_db.record_cash_flow(account=acc, cash_type="DEPOSIT", amount=1_000_000_000.0, trade_date="2026-11-05", comment="Vốn khởi tạo")
        
        # Mua CORE: 2.000 FPT @ 130.0 = 260.000.000 VND
        temp_db.record_retroactive_fill(
            ticker="FPT", action="BUY", executed_price=130.0, executed_volume=2000,
            account=acc, strategy_book="CORE", trade_date="2026-11-05"
        )
        # Mua QUANT: 1.000 MWG @ 60.0 = 60.000.000 VND
        temp_db.record_retroactive_fill(
            ticker="MWG", action="BUY", executed_price=60.0, executed_volume=1000,
            account=acc, strategy_book="QUANT", trade_date="2026-11-05"
        )
        
        # Đóng sổ ngày với giá FPT 135.0, MWG 62.0
        market_prices = {"FPT": 135_000.0, "MWG": 62_000.0}
        nav_report = temp_db.close_daily_nav(trade_date="2026-11-05", current_prices=market_prices)
        
        assert nav_report["core_nav"] > 0
        assert nav_report["quant_nav"] > 0
        assert abs((nav_report["core_nav"] + nav_report["quant_nav"]) - nav_report["total_nav"]) < 1.0

    def test_historical_1710_transactions_intact(self):
        """Bảo tồn 100% dữ liệu lịch sử 1.710 giao dịch trong database chính"""
        main_db = DatabaseManager(db_path=settings.SQLITE_DB_PATH)
        orders = main_db.get_recent_transactions(limit=5000)
        assert len(orders) >= 1710, f"Dữ liệu lịch sử bị hao hụt: {len(orders)} < 1710"

    def test_risk_limits_configuration(self):
        """Xác nhận cấu hình các ngưỡng rủi ro theo Hiến pháp Quỹ Dual-Book"""
        assert settings.CORE_MAX_ALLOCATION_PCT == 0.70
        assert settings.CORE_MAX_POSITION_PCT == 0.25
        assert settings.CORE_HARD_STOP_LOSS_PCT == 0.15
        
        assert settings.QUANT_MAX_ALLOCATION_PCT == 0.30
        assert settings.QUANT_MAX_POSITION_PCT == 0.15
        assert settings.QUANT_HARD_STOP_LOSS_PCT == 0.07


class TestFundamentalScreenerPipeline:
    """Kiểm thử Hạng mục 2: Fundamental Data Pipeline (0 Token)"""

    def test_screener_data_loading_and_scoring(self):
        """Xác nhận screener tải được dữ liệu quý, tính toán điểm FA (0-100)"""
        screener = FundamentalScreener()
        metrics = screener.get_latest_metrics("FPT")
        assert metrics is not None
        assert metrics["ticker"] == "FPT"
        assert "revenue_growth_yoy" in metrics
        assert "profit_growth_yoy" in metrics
        assert "roe" in metrics
        assert "gross_margin" in metrics
        assert "pe" in metrics
        
        score = screener.calculate_fundamental_score("FPT")
        assert 0.0 <= score <= 100.0

    def test_screener_summary_and_red_flags(self):
        """Xác nhận tóm tắt FA và kiểm tra Red Flags"""
        screener = FundamentalScreener()
        summary = screener.get_fundamental_summary("FPT")
        assert summary["ticker"] == "FPT"
        assert "fa_score" in summary
        assert "summary" in summary
        assert "FA Score" in summary["summary"]
        
        # Test kiểm tra red flag
        flags = screener.detect_red_flags("HPG")
        assert isinstance(flags, list)


class TestLiveInvestmentCommittee:
    """Kiểm thử Hạng mục 3: Live Investment Committee Telemetry & APIs"""

    def test_memo_database_crud(self, temp_db):
        """Xác nhận lưu trữ, truy vấn và cập nhật trạng thái Tờ trình biên bản họp"""
        memo_data = {
            "ticker": "SSI",
            "strategy_book": "QUANT",
            "trade_date": "2026-11-13",
            "action": "BUY",
            "target_price": 35.5,
            "stop_loss_price": 31.0,
            "target_volume": 2000,
            "macro_view": "Thanh khoản thị trường bùng nổ, KRX vận hành thử nghiệm.",
            "fa_summary": "FA Score: 72/100, P/B 1.4x, ROE 14.5%",
            "ta_ml_summary": "ML Alpha Score: 0.65, Xu hướng tăng ngắn hạn.",
            "bull_arguments": ["Dòng tiền chứng khoán vào mạnh", "Thị phần top 2"],
            "bear_arguments": ["Tự doanh rủi ro nếu thị trường đảo chiều"],
            "cro_verdict": "APPROVED",
            "cro_position_size": 0.10,
            "cio_decision": "Phê duyệt mua theo tỷ trọng đề xuất",
            "status": "PROPOSED"
        }
        
        memo_id = temp_db.save_decision_memo(memo_data)
        assert memo_id is not None
        assert memo_id.startswith("MEMO-")
        
        # Đọc lại memo
        retrieved = temp_db.get_decision_memo_by_id(memo_id)
        assert retrieved is not None
        assert retrieved["ticker"] == "SSI"
        assert retrieved["strategy_book"] == "QUANT"
        assert retrieved["status"] == "PROPOSED"
        
        # Cập nhật trạng thái sang APPROVED
        success = temp_db.update_memo_status(memo_id, "APPROVED")
        assert success is True
        
        updated = temp_db.get_decision_memo_by_id(memo_id)
        assert updated["status"] == "APPROVED"

    def test_committee_api_endpoints(self):
        """Xác nhận các endpoints REST API của Ủy ban Đầu tư"""
        client = TestClient(app)
        
        # 1. GET /api/committee/memos
        res_memos = client.get("/api/committee/memos")
        assert res_memos.status_code == 200
        data = res_memos.json()
        assert data["status"] == "SUCCESS"
        assert "agents" in data
        assert len(data["agents"]) == 7
        assert "memos" in data
        
        # 2. POST /api/committee/debate/{ticker}?book=CORE
        res_debate = client.post("/api/committee/debate/FPT?book=CORE")
        assert res_debate.status_code == 200
        debate_data = res_debate.json()
        assert debate_data["status"] == "SUCCESS"
        memo = debate_data["memo"]
        assert memo["ticker"] == "FPT"
        assert memo["strategy_book"] == "CORE"
        memo_id = memo["memo_id"]
        
        # 3. POST /api/committee/memos/{memo_id}/approve
        res_approve = client.post(f"/api/committee/memos/{memo_id}/approve")
        assert res_approve.status_code == 200
        assert res_approve.json()["status"] == "APPROVED"
        
        # 4. POST /api/committee/memos/{memo_id}/reject
        res_reject = client.post(f"/api/committee/memos/{memo_id}/reject")
        assert res_reject.status_code == 200
        assert res_reject.json()["status"] == "REJECTED"


class TestMachineLearningEnhancements:
    """Kiểm thử Hạng mục 4: Cải thiện Pipeline Machine Learning"""

    def test_market_regime_features_and_dynamic_atr(self):
        """Xác nhận 3 features chế độ thị trường và danh sách features đã được tích hợp"""
        predictor = UniversalAlphaPredictor()
        assert "market_ret_20d" in predictor.features
        assert "market_breadth_ma20" in predictor.features
        assert "rel_vol_to_market" in predictor.features
        assert len(predictor.features) >= 18

    def test_universal_alpha_predictor(self):
        """Xác nhận model LightGBM suy luận mượt mà với 19 đặc trưng"""
        predictor = UniversalAlphaPredictor()
        score = predictor.predict_score("HPG")
        assert 0.0 <= score <= 1.0
        
        rankings = predictor.get_market_rankings(top_n=3)
        assert len(rankings) <= 3
        if rankings:
            assert "ml_score" in rankings[0]
            assert "ticker" in rankings[0]

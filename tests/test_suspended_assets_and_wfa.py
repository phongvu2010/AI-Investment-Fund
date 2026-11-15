"""
Bộ kiểm thử Tự động cho 2 Tính Năng Nâng Cấp:
1. Quản trị Tài Sản Đóng Băng (Suspended / Delisted / Frozen Assets) & Liquid NAV
2. Cỗ máy Kiểm định Đa Chu Kỳ Walk-Forward Analysis (WFA) cho Backtest Lab
"""

import pytest
from datetime import date
from pathlib import Path
import tempfile
import sqlite3

from config import settings
from core.accounting.db_manager import DatabaseManager
from ai_brain.harness.guardrail_middleware import GuardrailMiddleware
from core.backtest.runner import BacktestRunner
from core.backtest.strategy_template import VSAMomentumStrategy
from core.backtest.report_adapter import BacktestReportAdapter


@pytest.fixture
def temp_db():
    """Tạo database SQLite tạm thời để kiểm thử độc lập"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    db = DatabaseManager(db_path=db_path)
    db.init_db(initial_capital=1_000_000_000.0)
    yield db
    
    # Dọn dẹp
    if db_path.exists():
        db_path.unlink()


def test_suspended_assets_lifecycle(temp_db):
    """Kiểm tra toàn bộ vòng đời quản trị tài sản đóng băng (CRUD & Tra cứu)"""
    # 1. Kiểm tra seed FLC mặc định
    is_susp, info = temp_db.is_asset_suspended("FLC")
    assert is_susp is True
    assert info["status"] == "DELISTED"
    assert info["provision_rate"] == 1.0

    # 2. Thêm mới một mã bị đình chỉ giao dịch (ví dụ: ROS)
    temp_db.set_asset_suspension(
        ticker="ROS",
        status="SUSPENDED",
        reason="Đình chỉ giao dịch do chậm nộp BCTC kiểm toán",
        provision_rate=0.80,
        recovery_estimated_price=500.0
    )

    is_ros_susp, ros_info = temp_db.is_asset_suspended("ROS")
    assert is_ros_susp is True
    assert ros_info["status"] == "SUSPENDED"
    assert ros_info["provision_rate"] == 0.80
    assert ros_info["recovery_estimated_price"] == 500.0

    # 3. Lấy danh sách toàn bộ
    all_susp = temp_db.get_suspended_assets()
    tickers = [a["ticker"] for a in all_susp]
    assert "FLC" in tickers
    assert "ROS" in tickers

    # 4. Gỡ bỏ trạng thái đình chỉ
    temp_db.remove_asset_suspension("ROS")
    is_ros_after, _ = temp_db.is_asset_suspended("ROS")
    assert is_ros_after is False


def test_guardrail_veto_dynamic_suspended_assets(temp_db):
    """Kiểm tra GuardrailMiddleware chặn đứng các mã bị đình chỉ tra cứu động từ DB"""
    guardrail = GuardrailMiddleware(db_manager=temp_db)

    # FLC đã có sẵn trong danh sách đóng băng
    is_valid, reason, score = guardrail.validate_order(
        ticker="FLC", action="BUY", proposed_price=5.0, proposed_volume=1000
    )
    assert is_valid is False
    assert "CRO VETO [SUSPENDED ASSET]" in reason
    assert score.value == 1.0

    # Mã bình thường (HPG) không bị đình chỉ
    temp_db.set_asset_suspension("TGG", status="DELISTED", reason="Vi phạm pháp luật")
    is_valid_tgg, reason_tgg, score_tgg = guardrail.validate_order(
        ticker="TGG", action="BUY", proposed_price=2.0, proposed_volume=1000
    )
    assert is_valid_tgg is False
    assert "CRO VETO [SUSPENDED ASSET]" in reason_tgg


def test_mark_to_market_liquid_nav_and_provision(temp_db):
    """Kiểm tra tính toán Liquid NAV và trích lập dự phòng tổn thất khi chốt sổ"""
    today_str = date.today().strftime("%Y-%m-%d")

    # Giả lập danh mục: có HPG (active) và FLC (delisted, provision 100%)
    with temp_db.get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO portfolio (account, ticker, strategy_book, quantity, avg_buy_price, current_price, market_value)
            VALUES 
                ('0001716319', 'HPG', 'QUANT', 1000.0, 25000.0, 26000.0, 26000000.0),
                ('0001716319', 'FLC', 'QUANT', 5000.0, 10000.0, 0.0, 0.0);
        """)
        conn.commit()

    current_prices = {"HPG": 26.0}  # Nghìn đồng -> 26,000 đ
    res = temp_db.close_daily_nav(trade_date=today_str, current_prices=current_prices)

    # Tiền mặt khởi điểm là 1 tỷ
    assert res["stock_value"] == 26_000_000.0
    assert res["liquid_stock_value"] == 26_000_000.0
    assert res["frozen_assets_value"] == 0.0
    # Dự phòng FLC: 5000 CP * 10,000 = 50,000,000 VND
    assert res["provision_loss"] == 50_000_000.0
    assert res["liquid_nav"] == res["cash_balance"] + 26_000_000.0
    assert res["total_nav"] == res["liquid_nav"]

    # Kiểm tra get_portfolio trả về status
    pf = temp_db.get_portfolio()
    flc_item = next((p for p in pf if p["ticker"] == "FLC"), None)
    assert flc_item is not None
    assert flc_item["asset_status"] == "DELISTED"
    assert flc_item["is_liquid"] is False
    assert flc_item["available_quantity"] == 0.0


def test_walk_forward_analysis_execution():
    """Kiểm thử Cỗ máy Walk-Forward Analysis (WFA) chạy đa cửa sổ trượt"""
    runner = BacktestRunner(initial_cash=100_000_000.0)

    # Chạy WFA trên mã HPG với 3 folds
    wfa_result = runner.run_walk_forward_analysis(
        strategy_class=VSAMomentumStrategy,
        tickers="HPG",
        days=500,
        n_splits=3,
        train_ratio=0.70,
        window_type="rolling",
        strategy_name="VSA Momentum Test"
    )

    assert wfa_result["strategy_name"] == "VSA Momentum Test"
    assert wfa_result["n_splits"] == 3
    assert len(wfa_result["folds"]) == 3
    assert wfa_result["verdict"] in ["INSTITUTIONAL_ROBUST", "ACCEPTABLE_ROBUST", "FRAGILE_OVERFIT"]

    summary = wfa_result["summary"]
    assert "wfe_sharpe_pct" in summary
    assert "avg_oos_sharpe" in summary
    assert "profitable_folds" in summary
    assert summary["total_folds"] == 3

    # Kiểm tra từng fold có đầy đủ IS và OOS
    for f in wfa_result["folds"]:
        assert "in_sample" in f
        assert "out_of_sample" in f
        assert f["in_sample"]["sharpe"] is not None
        assert f["out_of_sample"]["sharpe"] is not None


def test_walk_forward_report_adapter_and_cro_eval():
    """Kiểm thử Adapter biên tập báo cáo WFA và Thẩm định CRO đa chu kỳ"""
    runner = BacktestRunner(initial_cash=100_000_000.0)
    wfa_result = runner.run_walk_forward_analysis(
        strategy_class=VSAMomentumStrategy,
        tickers="HPG",
        days=400,
        n_splits=2,
        train_ratio=0.70
    )

    # 1. Thẩm định CRO với WFA
    metrics = {"sharpe_ratio": 1.5, "max_drawdown": -0.10, "profit_factor": 2.0, "total_trades": 20, "cagr": 0.25}
    cro_eval = BacktestReportAdapter.evaluate_cro_rules(metrics=metrics, wfa_report=wfa_result)
    assert "check_wfa" in cro_eval
    assert cro_eval["check_wfa"][0] is True or cro_eval["check_wfa"][0] is False

    # 2. Sinh báo cáo Markdown WFA
    md = BacktestReportAdapter.generate_walk_forward_markdown_report(wfa_result)
    assert "# 🔬 BÁO CÁO WALK-FORWARD ANALYSIS" in md
    assert "MA TRẬN CHI TIẾT CÁC BƯỚC TRƯỢT" in md
    assert "Fold #1" in md

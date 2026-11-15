"""
Kiểm thử Toàn diện các Tinh chỉnh Khắc phục 4 Rủi ro Trọng yếu:
1. Rủi ro 1: Lưu trữ CSDL & Cập nhật BCTC Động (Không phụ thuộc Seed cố định)
2. Rủi ro 2: Kiểm soát T+2.5 & Cổ phiếu Khả dụng bán (Available Quantity Guard)
3. Rủi ro 3: Tranh biện Hội đồng Đầu tư AI Đa chiều Thích nghi (Dynamic Debate Engine)
4. Rủi ro 4: Chống Overfitting với In-Sample & Out-of-Sample Verification
"""

import pytest
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
import polars as pl

from config import settings
from core.accounting.db_manager import DatabaseManager
from core.quant.fundamental_screener import FundamentalScreener
from ai_brain.engines.investment_debate_engine import InvestmentDebateEngine
from core.backtest.strategy_optimizer import StrategyOptimizerEngine

@pytest.fixture
def temp_db(tmp_path):
    """Fixture tạo CSDL SQLite cô lập trong thư mục tạm"""
    db_file = tmp_path / "test_refinements.db"
    db = DatabaseManager(db_path=db_file)
    db.init_db(initial_capital=1_000_000_000.0)
    return db

# ====================================================================
# TEST 1: RỦI RO 1 - CSDL BCTC & CẬP NHẬT ĐỘNG
# ====================================================================
def test_fundamental_database_storage_and_dynamic_update(temp_db, tmp_path):
    """Kiểm tra lưu trữ BCTC vào SQLite và cập nhật động không phụ thuộc seed"""
    screener_file = tmp_path / "temp_fundamentals.parquet"
    screener = FundamentalScreener(data_path=screener_file)
    screener.db = temp_db

    # 1. Thêm chỉ số BCTC mới hoàn toàn cho mã TTT (Doanh nghiệp sản xuất mẫu)
    custom_metrics = {
        "ticker": "TTT",
        "period": "2026Q3",
        "year": 2026,
        "quarter": 3,
        "revenue_growth_yoy": 0.25,
        "profit_growth_yoy": 0.35,
        "roe": 0.22,
        "gross_margin": 0.32,
        "debt_to_equity": 0.45,
        "ocf_to_net_income": 1.30,
        "pe": 10.5,
        "pb": 1.6,
        "pe_5y_median": 12.0,
        "piotroski_f_score": 8,
        "altman_z_score": 3.8,
        "notes": "Doanh nghiệp tăng trưởng mạnh quý 3"
    }

    success = screener.upsert_company_financials(custom_metrics)
    assert success is True

    # 2. Truy vấn trực tiếp từ SQLite Database
    db_row = temp_db.get_latest_fundamental("TTT")
    assert db_row is not None
    assert db_row["ticker"] == "TTT"
    assert db_row["period"] == "2026Q3"
    assert db_row["roe"] == 0.22

    # 3. Chấm điểm cơ bản thông qua FundamentalScreener
    summary = screener.get_fundamental_summary("TTT")
    assert summary["ticker"] == "TTT"
    assert summary["fa_score"] >= 80.0
    assert summary["rating"] in ("BUY", "STRONG_BUY")
    assert len(summary["red_flags"]) == 0

# ====================================================================
# TEST 2: RỦI RO 2 - KIỂM SOÁT T+2.5 VÀ KHẢ DỤNG BÁN
# ====================================================================
def test_t25_settlement_and_available_quantity(temp_db):
    """Kiểm tra quy chế T+2.5: Cấm bán khi hàng chưa về, cho phép bán khi đã đủ 2 ngày giao dịch"""
    account = "0001716319"
    ticker = "HPG"

    # Giả lập mua 10,000 CP vào Thứ 2 (2026-11-09)
    buy_date = "2026-11-09" # Thứ 2
    temp_db.record_retroactive_fill(
        ticker=ticker,
        action="BUY",
        executed_price=28.5,
        executed_volume=10_000,
        trade_date=buy_date,
        account=account,
        strategy_book="QUANT"
    )

    # 1. Kiểm tra tại ngày T (Thứ 2: 2026-11-09)
    avail_t0 = temp_db.calculate_available_shares(ticker, account=account, as_of_date="2026-11-09")
    assert avail_t0["total_quantity"] == 10_000
    assert avail_t0["available_quantity"] == 0
    assert avail_t0["pending_settlement_quantity"] == 10_000

    # Cố gắng đặt lệnh BÁN tại ngày T0 -> BẮT BUỘC BỊ CRO VETO CHẶN
    with pytest.raises(ValueError, match="CRO VETO \\[T\\+2.5 SETTLEMENT\\]"):
        temp_db.create_proposed_order(
            ticker=ticker,
            action="SELL",
            proposed_price=30.0,
            proposed_volume=5_000,
            trade_date="2026-11-09",
            account=account,
            strategy_book="QUANT"
        )

    # 2. Kiểm tra tại ngày T+1 (Thứ 3: 2026-11-10) -> Vẫn chưa về khả dụng
    avail_t1 = temp_db.calculate_available_shares(ticker, account=account, as_of_date="2026-11-10")
    assert avail_t1["available_quantity"] == 0
    assert avail_t1["pending_settlement_quantity"] == 10_000

    with pytest.raises(ValueError, match="CRO VETO \\[T\\+2.5 SETTLEMENT\\]"):
        temp_db.create_proposed_order(
            ticker=ticker,
            action="SELL",
            proposed_price=30.0,
            proposed_volume=1_000,
            trade_date="2026-11-10",
            account=account,
            strategy_book="QUANT"
        )

    # 3. Kiểm tra tại ngày T+2 (Thứ 4: 2026-11-11) -> Đủ 2 ngày giao dịch (Chiều T+2 hàng về)
    avail_t2 = temp_db.calculate_available_shares(ticker, account=account, as_of_date="2026-11-11")
    assert avail_t2["available_quantity"] == 10_000
    assert avail_t2["pending_settlement_quantity"] == 0

    # Đặt lệnh BÁN tại ngày T+2 -> HỢP LỆ VÀ THÀNH CÔNG
    order_id = temp_db.create_proposed_order(
        ticker=ticker,
        action="SELL",
        proposed_price=30.0,
        proposed_volume=5_000,
        trade_date="2026-11-11",
        account=account,
        strategy_book="QUANT"
    )
    assert order_id.startswith("ORD-")

    # 4. Kiểm tra bán quá số lượng khả dụng -> BỊ CHẶN
    with pytest.raises(ValueError, match="CRO VETO \\[T\\+2.5 SETTLEMENT\\]"):
        temp_db.create_proposed_order(
            ticker=ticker,
            action="SELL",
            proposed_price=30.0,
            proposed_volume=15_000,  # Vượt quá 10,000 khả dụng
            trade_date="2026-11-11",
            account=account,
            strategy_book="QUANT"
        )

def test_t25_weekend_handling(temp_db):
    """Kiểm tra quy chế T+2.5 khi mua vào Thứ 6 (loại bỏ Thứ 7 và CN)"""
    account = "0001716319"
    ticker = "FPT"

    # Mua vào Thứ 6 (2026-11-06)
    temp_db.record_retroactive_fill(
        ticker=ticker,
        action="BUY",
        executed_price=135.0,
        executed_volume=1_000,
        trade_date="2026-11-06", # Thứ 6
        account=account,
        strategy_book="CORE"
    )

    # Thứ 7 (2026-11-07) -> Không phải ngày giao dịch, available = 0
    assert temp_db.calculate_available_shares(ticker, account=account, as_of_date="2026-11-07")["available_quantity"] == 0

    # Thứ 2 tuần sau (2026-11-09) -> Mới trôi qua 1 ngày giao dịch (T+1), available = 0
    assert temp_db.calculate_available_shares(ticker, account=account, as_of_date="2026-11-09")["available_quantity"] == 0

    # Thứ 3 tuần sau (2026-11-10) -> Đã trôi qua 2 ngày giao dịch (T+2), hàng về khả dụng = 1,000 CP
    assert temp_db.calculate_available_shares(ticker, account=account, as_of_date="2026-11-10")["available_quantity"] == 1_000

# ====================================================================
# TEST 3: RỦI RO 3 - ĐỘNG CƠ TRANH BIỆN ĐA CHIỀU (DYNAMIC DEBATE)
# ====================================================================
def test_dynamic_debate_engine_output():
    """Kiểm tra động cơ sinh luận điểm đối kháng Bull vs Bear thích ứng theo số liệu thực"""
    engine = InvestmentDebateEngine()

    mock_regime = {
        "regime": "UPTREND",
        "breadth_ma20_pct": 75.0,
        "description": "Thị trường tăng trưởng tích cực"
    }

    mock_fa_healthy = {
        "fa_score": 85.0,
        "rating": "STRONG_BUY",
        "metrics": {
            "revenue_growth_yoy": 0.22,
            "profit_growth_yoy": 0.30,
            "roe": 0.25,
            "pe": 12.0,
            "pe_5y_median": 15.0,
            "pb": 1.8,
            "debt_to_equity": 0.35,
            "ocf_to_net_income": 1.25,
            "piotroski_f_score": 8,
            "altman_z_score": 3.5
        },
        "red_flags": []
    }

    # Sinh tranh biện cho Sổ CORE
    debate_core = engine.generate_debate(
        ticker="HPG",
        strategy_book="CORE",
        market_regime_info=mock_regime,
        fa_res=mock_fa_healthy,
        ml_score=0.45,
        latest_close=28.5,
        support_price=26.5,
        resistance_price=32.5
    )

    assert "bull_arguments" in debate_core
    assert "bear_arguments" in debate_core
    assert len(debate_core["bull_arguments"]) > 50
    assert len(debate_core["bear_arguments"]) > 50
    # Phe Bò phải đề cập đến FA và tăng trưởng
    assert "FA" in debate_core["bull_arguments"] or "tăng trưởng" in debate_core["bull_arguments"]
    # Phe Gấu phải đề cập đến cản kỹ thuật hoặc rủi ro
    assert "cản" in debate_core["bear_arguments"] or "rủi ro" in debate_core["bear_arguments"]

# ====================================================================
# TEST 4: RỦI RO 4 - PHÂN TÁCH DỮ LIỆU & CHỐNG OVERFITTING
# ====================================================================
def test_overfitting_guard_evaluation():
    """Kiểm tra logic phân tích Out-of-Sample và phát hiện bẫy Overfitting"""
    optimizer = StrategyOptimizerEngine()

    # 1. Kiểm tra chia tách chuỗi dữ liệu 70% In-Sample / 30% Out-of-Sample
    sample_df = pl.DataFrame({
        "Date": [f"2026-01-{i:02d}" for i in range(1, 101)],
        "Close": [10.0 + i for i in range(100)]
    })
    data_dict = {"HPG": sample_df}
    in_s, out_s = optimizer.split_train_test_data(data_dict, train_ratio=0.70)
    assert len(in_s["HPG"]) == 70
    assert len(out_s["HPG"]) == 30

    # 2. Trường hợp ROBUST: Out-of-Sample giữ vững hiệu suất
    is_metrics_good = {"sharpe_ratio": 1.80, "max_drawdown_pct": 10.0, "cagr_pct": 25.0, "win_rate_pct": 60.0, "total_trades": 30}
    oos_metrics_good = {"sharpe_ratio": 1.50, "max_drawdown_pct": 12.0, "cagr_pct": 20.0, "win_rate_pct": 58.0, "total_trades": 12}
    eval_good = optimizer.evaluate_overfitting_guard(is_metrics_good, oos_metrics_good)
    assert eval_good["verdict"] == "ROBUST"
    assert eval_good["status"] == "PASS"
    assert eval_good["sharpe_retention_pct"] >= 80.0

    # 3. Trường hợp OVERFITTED: In-Sample Sharpe cao nhưng Out-of-Sample sụp đổ
    is_metrics_overfit = {"sharpe_ratio": 2.20, "max_drawdown_pct": 8.0, "cagr_pct": 35.0, "win_rate_pct": 70.0, "total_trades": 40}
    oos_metrics_collapsed = {"sharpe_ratio": 0.25, "max_drawdown_pct": 28.0, "cagr_pct": -5.0, "win_rate_pct": 35.0, "total_trades": 15}
    eval_bad = optimizer.evaluate_overfitting_guard(is_metrics_overfit, oos_metrics_collapsed)
    assert eval_bad["verdict"] == "OVERFITTED"
    assert eval_bad["status"] == "REJECTED"
    assert "CẢNH BÁO BẪY OVERFITTING" in eval_bad["assessment"]

# ====================================================================
# TEST 5: TINH CHỈNH 1 - DỮ LIỆU INTRADAY ĐA NGUỒN & CASCADING FALLBACK
# ====================================================================
def test_intraday_multi_source_and_fallback():
    """Kiểm tra động cơ dữ liệu đa nguồn: không bao giờ crash và tự động fallback về Parquet"""
    from core.data.intraday_data_feed import IntradayDataFeed

    feed = IntradayDataFeed()
    health = feed.get_feed_health()
    assert "providers" in health
    assert "PARQUET_FALLBACK" in health["providers"]

    # Lấy nến HPG (sẽ fallback an toàn về Parquet nếu môi trường sandbox không có mạng)
    bar = feed.get_live_bar("HPG")
    assert bar is not None
    assert bar["ticker"] == "HPG"
    assert bar["close"] > 0
    assert "source" in bar
    assert "is_floor_locked" in bar
    assert "floor_price" in bar
    assert "ceiling_price" in bar

# ====================================================================
# TEST 6: TINH CHỈNH 2 - CRO VETO CHIẾN LƯỢC BỊ BẪY OVERFITTING
# ====================================================================
def test_anti_overfitting_cro_veto():
    """Kiểm tra Giám đốc Rủi ro (CRO) bắt buộc VETO nếu chiến lược bị Overfitting dù Sharpe In-Sample rất cao"""
    from core.backtest.report_adapter import BacktestReportAdapter

    # Giả lập metrics In-Sample rất cao (Sharpe 2.50, MDD 8%, PF 2.2, 40 lệnh)
    full_metrics = {
        "sharpe_ratio": 2.50,
        "max_drawdown": -0.08,
        "profit_factor": 2.20,
        "win_rate": 0.65,
        "total_trades": 40,
        "cagr": 0.35
    }

    # Báo cáo Overfitting: OOS Sharpe sụp đổ về 0.30 (< 0.50)
    overfit_report = {
        "verdict": "OVERFITTED",
        "status": "REJECTED",
        "assessment": "🚩 CẢNH BÁO BẪY OVERFITTING: Out-of-Sample Sharpe tụt xuống 0.30.",
        "in_sample": {"sharpe": 2.50, "mdd_pct": 8.0, "cagr_pct": 35.0, "win_rate_pct": 65.0, "total_trades": 30},
        "out_of_sample": {"sharpe": 0.30, "mdd_pct": 25.0, "cagr_pct": -2.0, "win_rate_pct": 30.0, "total_trades": 10},
        "sharpe_retention_pct": 12.0,
        "sharpe_decay_pct": 88.0
    }

    # Đánh giá CRO
    cro_eval = BacktestReportAdapter.evaluate_cro_rules(full_metrics, overfit_report=overfit_report)
    assert cro_eval["status"] == "REJECTED"
    assert "BẪY OVERFITTING" in cro_eval["verdict"]
    assert cro_eval["check_overfit"][0] is False

    # Báo cáo Markdown phải chứa Section 3 thẩm định Out-of-Sample
    dummy_result = {
        "strategy_name": "Test Overfit Strategy",
        "tickers": ["HPG"],
        "metrics": full_metrics,
        "overfit_report": overfit_report
    }
    md_report = BacktestReportAdapter.generate_markdown_report(dummy_result)
    assert "THẨM ĐỊNH CHỐNG OVERFITTING" in md_report
    assert "Giữ vững **12.0%**" in md_report

# ====================================================================
# TEST 7: TINH CHỈNH 3 - PHÒNG VỆ RỦI RO KẸT SÀN / TRẮNG BÊN MUA
# ====================================================================
def test_floor_lock_detection_and_cro_defense():
    """Kiểm tra phát hiện Kẹt sàn (Floor-lock) và phân tích độ sâu sổ lệnh"""
    from core.data.intraday_data_feed import IntradayDataFeed
    from core.data.parquet_manager import ParquetMarketDataManager

    feed = IntradayDataFeed()
    pm = ParquetMarketDataManager()

    # 1. Kiểm tra hàm check_floor_lock_risk
    risk = feed.check_floor_lock_risk("HPG")
    assert "risk_level" in risk
    assert "is_floor_locked" in risk
    assert "floor_price" in risk
    assert risk["risk_level"] in ("NORMAL", "WARNING_NEAR_FLOOR", "EMERGENCY_FLOOR_LOCKED")

    # 2. Kiểm tra tính năng liquidity metrics kèm phân tích căng thẳng kẹt sàn
    liq_stats = pm.get_ticker_liquidity_metrics("HPG", window=20)
    assert "liquidity_stress_score" in liq_stats
    assert "is_floor_risk_high" in liq_stats
    assert "is_currently_floor_locked" in liq_stats
    assert "max_consecutive_floor_days" in liq_stats

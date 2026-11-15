"""
Điểm Khởi Chạy Trung Tâm của Quỹ Đầu tư AI (Fund Main Orchestrator).
Kết nối toàn bộ Não bộ Multi-Agent, Cơ sở Dữ liệu, Động cơ Backtest và Dashboard.
"""

import sys
import argparse
import time
from pathlib import Path
from datetime import date
from typing import Optional

from config import settings
from core.accounting.db_manager import DatabaseManager
from core.data.parquet_manager import ParquetMarketDataManager
from core.quant.fundamental_screener import FundamentalScreener
from core.quant.ml_predictor import UniversalAlphaPredictor
from ai_brain.engines.investment_debate_engine import InvestmentDebateEngine
from ai_brain.engines.jev_decision_engine import JevDecisionEngine
from ai_brain.harness.context_manager import HarnessContextManager
from ai_brain.harness.guardrail_middleware import GuardrailMiddleware, GuardrailVetoException

def print_banner():
    banner = """
    ╔═══════════════════════════════════════════════════════════════════╗
    ║             🏛️  AI PERSONAL INVESTMENT FUND SYSTEM  🏛️            ║
    ║   Autonomous Multi-Agent Hedge Fund • Vietnam Stock Market (VN)   ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """
    print(banner)

def show_status():
    """Hiển thị tổng quan tình trạng hoạt động của Quỹ"""
    print_banner()
    db = DatabaseManager()
    parquet_mgr = ParquetMarketDataManager()

    nav_info = db.get_latest_nav() or {}
    portfolio = db.get_portfolio()
    pq_summary = parquet_mgr.get_summary()

    total_nav = float(nav_info.get('total_nav', settings.INITIAL_CAPITAL))
    liquid_nav = float(nav_info.get('liquid_nav', total_nav))
    if liquid_nav <= 0:
        liquid_nav = total_nav

    frozen_assets = float(nav_info.get('frozen_assets_value', 0.0))
    provision_loss = float(nav_info.get('provision_loss', 0.0))

    print("📊 [1] TÌNH HÌNH TÀI SẢN & VỐN (NAV):")
    print(f"   • Tổng Tài sản Ròng (NAV): {total_nav:,.0f} VND")
    print(f"   • NAV Khả dụng (Liquid):  {liquid_nav:,.0f} VND")
    print(f"   • Tiền mặt khả dụng:      {nav_info.get('cash_balance', settings.INITIAL_CAPITAL):,.0f} VND")
    print(f"   • Giá trị Cổ phiếu:       {nav_info.get('stock_value', 0.0):,.0f} VND")
    if frozen_assets > 0 or provision_loss > 0:
        print(f"   • Tài sản Đóng băng:      {frozen_assets:,.0f} VND (Dự phòng tổn thất: {provision_loss:,.0f} VND)")
    print(f"   • Biến động ngày:         {nav_info.get('daily_pnl', 0.0):+,.0f} VND ({nav_info.get('daily_pnl_pct', 0.0):+.2f}%)")
    print(f"   • Lợi nhuận lũy kế:       {nav_info.get('cumulative_pnl', 0.0):+,.0f} VND")

    print("\n📦 [2] DANH MỤC NẮM GIỮ (PORTFOLIO):")
    if not portfolio:
        print("   • Đang giữ 100% Tiền mặt.")
    else:
        for item in portfolio:
            status_tag = f" ⚠️ [{item.get('asset_status')}]" if item.get('asset_status') and item.get('asset_status') != 'ACTIVE' else ""
            print(f"   • {item['ticker']}{status_tag}: {item['quantity']:,} CP | Giá vốn: {item['avg_buy_price']:,.2f} | Thị giá: {item.get('current_price', 0):,.2f} | PnL: {item.get('unrealized_pnl', 0):+,.0f} VND ({item.get('unrealized_pnl_pct', 0):+.2f}%)")

    print("\n💾 [3] KHO DỮ LIỆU ĐỊNH LƯỢNG (PARQUET 5 NĂM):")
    if pq_summary["status"] == "READY":
        print(f"   • Trạng thái: SẴN SÀNG | {pq_summary['total_rows']:,} dòng nến | {pq_summary['total_tickers']} mã CP")
        print(f"   • Chuỗi thời gian: từ {pq_summary['from_date']} đến {pq_summary['to_date']} (Dung lượng: {pq_summary['file_size_mb']} MB)")
    else:
        print("   • Trạng thái: CHƯA CÓ FILE (Hãy chạy: python tools/bigquery_sync.py --mode demo)")

    print("\n🤖 [4] NÃO BỘ MULTI-AGENT (.agent):")
    skills_dir = settings.BASE_DIR / ".agent" / "skills"
    agents_dir = settings.BASE_DIR / ".agent" / "agents"
    rules_dir = settings.BASE_DIR / ".agent" / "rules"

    num_skills = len(list(skills_dir.glob("strategy-*"))) if skills_dir.exists() else 0
    num_agents = len(list(agents_dir.glob("*.md"))) if agents_dir.exists() else 0
    num_rules = len(list(rules_dir.glob("*.md"))) if rules_dir.exists() else 0

    print(f"   • Quy chế Kỷ luật Quỹ:  {num_rules} văn bản (.agent/rules/)")
    print(f"   • Nhân sự AI Agents:    {num_agents} vị trí (.agent/agents/)")
    print(f"   • Kỹ năng Chiến lược:   {num_skills} skills (.agent/skills/)")
    print("=" * 73)

def run_workflow_morning():
    """Chạy Workflow 01: Bản tin Sáng (Morning Briefing) kết hợp Jev AI System 1 Triage"""
    print_banner()
    print("☀️ BẮT ĐẦU WORKFLOW 01: BẢN TIN TIỀN THỊ TRƯỜNG (08:00 AM)...")
    parquet_mgr = ParquetMarketDataManager()
    jev = JevDecisionEngine()
    
    print("\n1. Quét tìm các mã có dòng tiền vào mạnh (Volume > 1.2x MA20 Volume)...")
    candidates = parquet_mgr.scan_breakout_vol_candidates(min_vol_ratio=1.1, limit=10)
    
    if candidates:
        print(f"🎯 Phát hiện {len(candidates)} mã cổ phiếu đạt tiêu chí Watchlist:")
        for c in candidates:
            # Jev AI System 1 Reflex Triage
            noul_triage = jev.triage_market_event(
                c['ticker'],
                intraday_bar={"pct_change": c['diff_ma20_pct'], "vol_ratio": c['vol_ratio']}
            )
            route_choice = jev.route_strategy_book(c['ticker'])
            triage_label = "MATERIAL" if noul_triage.value else "NOISE"
            print(f"   • {c['ticker']}: Thị giá {c['close']} | Đột biến Vol: {c['vol_ratio']}x | Trên MA20: +{c['diff_ma20_pct']}% | Jev [{triage_label}] (Conf: {noul_triage.confidence*100:.0f}%, {noul_triage.latency_ms:.1f}ms) -> Sổ: [{route_choice.value}]")
    else:
        print("ℹ️ Phiên hôm nay chưa có mã nào vượt ngưỡng volume đột biến.")

    print("\n2. Đánh giá Khí tượng Thị trường (Macro Agent):")
    print("   • Trạng thái đề xuất: [SIDEWAY / ACCUMULATION]")
    print("   • Chiến lược ưu tiên: Chỉ giải ngân thăm dò 30% khi có xác nhận vượt nền giá.")

def run_workflow_triage(ticker: Optional[str] = None):
    """Chạy Workflow Triage: Phản xạ nhanh thị trường System 1 Jev AI (< 500ms)"""
    print_banner()
    jev = JevDecisionEngine()
    parquet_mgr = ParquetMarketDataManager()

    if ticker:
        t = ticker.upper()
        print(f"⚡ ĐANG CHẠY PHẢN XẠ NHANH JEV AI SYSTEM 1 CHO MÃ [{t}]...")
        t0 = time.perf_counter()
        triage = jev.triage_market_event(t)
        route = jev.route_strategy_book(t)
        risk = jev.score_execution_risk(t, action="BUY", proposed_vol=1000)
        total_lat = (time.perf_counter() - t0) * 1000.0

        print(f"\n📊 KẾT QUẢ PHẢN XẠ SYSTEM 1 (Tổng thời gian: {total_lat:.2f}ms < 500ms):")
        print(f"1. Triage Sự Kiện (Noul): [{'MATERIAL' if triage.value else 'NOISE'}] (Conf: {triage.confidence*100:.1f}%, Latency: {triage.latency_ms:.2f}ms)")
        print(f"   • Lý do: {triage.reasoning}")
        print(f"2. Định Tuyến Sổ (Choice): [{route.value}] (Conf: {route.confidence*100:.1f}%, Latency: {route.latency_ms:.2f}ms)")
        print(f"   • Phân phối xác suất: {route.probabilities}")
        print(f"   • Lý do: {route.reasoning}")
        print(f"3. Chấm Điểm Rủi Ro (Score): {risk.value:.2f}/1.00 (Conf: {risk.confidence*100:.1f}%, Latency: {risk.latency_ms:.2f}ms)")
        print(f"   • Trạng thái Guardrail: {'AN TOÀN' if risk.value <= 0.70 else 'CẢNH BÁO NGUY HIỂM'}")
    else:
        print("⚡ ĐANG CHẠY QUÉT PHẢN XẠ NHANH TOÀN THỊ TRƯỜNG (SYSTEM 1)...")
        candidates = parquet_mgr.scan_breakout_vol_candidates(min_vol_ratio=1.1, limit=5)
        print(f"🔍 Đã quét {len(candidates)} mã có tín hiệu dòng tiền:")
        for c in candidates:
            tr = jev.triage_market_event(c["ticker"])
            rt = jev.route_strategy_book(c["ticker"])
            rk = jev.score_execution_risk(c["ticker"], action="BUY", proposed_vol=1000)
            print(f"   • {c['ticker']}: [{'MATERIAL' if tr.value else 'NOISE'}] | Sổ: [{rt.value}] | Risk: {rk.value:.2f} | Latency: {tr.latency_ms + rt.latency_ms + rk.latency_ms:.1f}ms")

def run_workflow_debate(ticker: str, strategy_book: str = "QUANT") -> Optional[dict]:
    """Chạy Workflow 02: Phiên Họp Ủy Ban Đầu Tư AI (6 Agents) kết hợp Jev AI System 1 & Harness"""
    print_banner()
    t = ticker.upper()
    book = strategy_book.upper()
    print(f"⚔️ BẮT ĐẦU WORKFLOW 02: HỘI ĐỒNG ĐẦU TƯ TRANH BIỆN MÃ [{t}] - SỔ [{book}]...")
    
    db = DatabaseManager()
    parquet_mgr = ParquetMarketDataManager()
    fa_screener = FundamentalScreener()
    ml_predictor = UniversalAlphaPredictor()
    jev = JevDecisionEngine()
    guardrail = GuardrailMiddleware(db)

    # Nạp ngữ cảnh thể chế từ Harness Context Manager
    harness_ctx = HarnessContextManager(db)
    prompt_ctx = harness_ctx.format_prompt_context(t, book)
    
    # 1. Thu thập dữ liệu kỹ thuật
    df = parquet_mgr.get_ticker_history(t, days=30)
    if len(df) == 0:
        print(f"❌ Không tìm thấy dữ liệu cho mã: {t}")
        return None
        
    latest_close = float(df["close"][-1])
    price_unit = "k" if latest_close < 1000.0 else "đ"
    norm_price = latest_close * 1000.0 if latest_close < 1000.0 else latest_close
    
    # 2. Agent 1: Macro Scout (Khí tượng Thị trường & Độ rộng Market Breadth 0 Token)
    regime_info = parquet_mgr.get_market_regime()
    regime = regime_info.get("regime", "SIDEWAY")
    macro_view = (
        f"[{regime}] {regime_info.get('description', '')} "
        f"Phân bổ đề xuất động: Core {regime_info.get('recommended_core_pct', 0.5)*100:.0f}%, "
        f"Quant {regime_info.get('recommended_quant_pct', 0.2)*100:.0f}%, "
        f"Cash {regime_info.get('recommended_cash_pct', 0.3)*100:.0f}%."
    )
    print(f"\n1. 🛰️ Macro Scout (Vĩ mô & Chu kỳ Thị trường):")
    print(f"   • Trạng thái: [{regime}] (Độ rộng: {regime_info.get('breadth_ma20_pct', 50)}% > MA20, {regime_info.get('breadth_ma50_pct', 50)}% > MA50)")
    print(f"   • Nhận định: {regime_info.get('description', '')}")
    print(f"   • Hạn mức đề xuất động: Core {regime_info.get('recommended_core_pct', 0.5)*100:.0f}% | Quant {regime_info.get('recommended_quant_pct', 0.2)*100:.0f}% | Tiền mặt: {regime_info.get('recommended_cash_pct', 0.3)*100:.0f}%")

    # 3. Agent 2: FA Analyst (Phân tích Cơ bản & BCTC 0 Token)
    fa_res = fa_screener.get_fundamental_summary(t)
    fa_score = fa_res["fa_score"]
    red_flags = fa_res["red_flags"]
    fa_summary = f"{fa_res['summary']} | Red Flags: {len(red_flags)}"
    print(f"\n2. 📑 Fundamental Analyst (FA):")
    print(f"   • FA Score: {fa_score}/100 ({fa_res['rating']})")
    print(f"   • Đánh giá: {fa_res['summary']}")
    if red_flags:
        for rf in red_flags:
            print(f"   • {rf}")

    # 4. Agent 3: Quant / Technical Analyst (TA & Machine Learning)
    ml_score = ml_predictor.predict_score(t)
    support_price = round(latest_close * 0.94, 2)
    resistance_price = round(latest_close * 1.15, 2)
    ta_ml_summary = f"ML Alpha Score: {ml_score:.4f} | Vùng hỗ trợ: {support_price:,.2f} | Kháng cự mục tiêu: {resistance_price:,.2f}"
    print(f"\n3. 🤖 Technical & Quant ML Analyst:")
    print(f"   • Thị giá: {latest_close:,.2f} {price_unit}")
    print(f"   • {ta_ml_summary}")

    # 5. Phản xạ Phân loại System 1 (Jev AI Decision Engine)
    pct_chg = round((latest_close - float(df["close"][-2])) / float(df["close"][-2]) * 100.0, 2) if len(df) > 1 else 0.0
    triage_noul = jev.triage_market_event(
        ticker=t,
        intraday_bar={"pct_change": pct_chg, "vol_ratio": 1.2},
        market_regime=regime_info
    )
    route_choice = jev.route_strategy_book(ticker=t, fa_summary=fa_res, ml_score=ml_score, regime=regime)

    print(f"\n⚡ [JEV AI SYSTEM 1 - REFLEX TELEMETRY]:")
    print(f"   • Triage Sự Kiện (Noul): [{'MATERIAL' if triage_noul.value else 'NOISE'}] (Conf: {triage_noul.confidence*100:.1f}%, Latency: {triage_noul.latency_ms:.2f}ms)")
    print(f"   • Định Tuyến Sổ (Choice): [{route_choice.value}] (P(Core)={route_choice.probabilities.get('CORE',0):.2f}, P(Quant)={route_choice.probabilities.get('QUANT',0):.2f}, P(Ignore)={route_choice.probabilities.get('IGNORE',0):.2f}, Latency: {route_choice.latency_ms:.2f}ms)")
    print(f"   • Nhận định: {route_choice.reasoning}")

    # 6. Khởi động Động cơ Tranh biện Hội đồng Đầu tư AI (Adversarial Multi-Agent Debate)
    # Ràng buộc kiến trúc: Chỉ kích hoạt LLM (System 2) khi Jev System 1 có confidence >= 0.75 và vượt qua bộ lọc sơ bộ
    passes_preliminary = (route_choice.value != "IGNORE")
    debate_engine = InvestmentDebateEngine()
    debate_result = debate_engine.generate_debate(
        ticker=t,
        strategy_book=book,
        market_regime_info=regime_info,
        fa_res=fa_res,
        ml_score=ml_score,
        latest_close=latest_close,
        support_price=support_price,
        resistance_price=resistance_price,
        jev_confidence=triage_noul.confidence,
        passes_filter=passes_preliminary
    )
    bull_arguments = debate_result["bull_arguments"]
    bear_arguments = debate_result["bear_arguments"]
    debate_engine_name = debate_result.get("engine", "MULTI_FACTOR")

    print(f"\n4. 🐂 Bull Advocate (Phe Bò) [{debate_engine_name}]:")
    for line in bull_arguments.split("\n"):
        print(f"   • {line}")

    print(f"\n5. 🐻 Bear Red-Team (Phe Gấu Phản Biện) [{debate_engine_name}]:")
    for line in bear_arguments.split("\n"):
        print(f"   • {line}")

    # 7. Agent 6: Chief Risk Officer (CRO Veto & Multi-Layer Risk Engine)
    liq_stats = parquet_mgr.get_ticker_liquidity_metrics(t, window=20)
    adv_20 = liq_stats.get("adv", 0.0)
    adtv_billion = liq_stats.get("adtv_billion", 0.0)
    is_liquid = liq_stats.get("is_liquid", True)
    max_liq_vol = liq_stats.get("max_allowed_vol", 0)

    # Lấy thông tin NAV và danh mục hiện tại để kiểm tra độ tập trung vị thế
    nav_info = db.get_latest_nav() or {}
    total_nav = nav_info.get("total_nav", settings.INITIAL_CAPITAL)
    cash_avail = db.get_current_cash()
    
    # Kiểm tra Circuit Breaker sụt giảm tuần
    weekly_dd = abs(nav_info.get("weekly_drawdown_pct", 0.0))
    is_circuit_breaker_active = weekly_dd > settings.MAX_WEEKLY_DRAWDOWN_PCT

    if book == "CORE":
        max_pct = settings.CORE_MAX_POSITION_PCT
        stop_loss_pct = settings.CORE_HARD_STOP_LOSS_PCT
    else:
        max_pct = settings.QUANT_MAX_POSITION_PCT
        stop_loss_pct = settings.QUANT_HARD_STOP_LOSS_PCT

    # Tính hạn mức tối đa theo trần NAV
    max_capital = total_nav * max_pct
    
    # Kiểm tra khối lượng đã nắm giữ trong danh mục để chống tập trung quá mức
    existing_positions = db.get_portfolio()
    curr_holding_vol = sum(p["quantity"] for p in existing_positions if p["ticker"] == t)
    curr_holding_val = curr_holding_vol * norm_price

    # Khối lượng mua thêm tối đa để không vượt trần vị thế
    remaining_capital = max(0.0, max_capital - curr_holding_val)
    target_vol = int((remaining_capital / norm_price) // 100) * 100
    stop_loss_price = round(latest_close * (1 - stop_loss_pct), 2)

    # Áp dụng Liquidity Capping (Tối đa 2.0% ADV để chống trượt giá trên thị trường thực)
    liquidity_adjusted = False
    if is_liquid and max_liq_vol > 0 and target_vol > max_liq_vol:
        target_vol = max_liq_vol
        liquidity_adjusted = True

    target_vol = max(100, target_vol) if target_vol > 0 else 0

    # Chấm điểm Rủi Ro Thực Thi qua Jev AI System 1
    portfolio_state = {
        "total_nav": total_nav,
        "current_position_value": curr_holding_val,
        "strategy_book": book,
        "weekly_drawdown_pct": weekly_dd,
        "available_quantity": target_vol
    }
    jev_risk = jev.score_execution_risk(
        ticker=t,
        action="BUY",
        proposed_vol=target_vol,
        liq_metrics=liq_stats,
        portfolio_state=portfolio_state,
        proposed_price=latest_close
    )

    # Phán quyết CRO theo cơ chế Đa tầng (Multi-Layer VETO)
    if is_circuit_breaker_active:
        cro_verdict = "VETO"
        cro_reason = f"CRO VETO [CIRCUIT BREAKER]: NAV sụt giảm tuần {weekly_dd*100:.1f}% vượt ngưỡng {settings.MAX_WEEKLY_DRAWDOWN_PCT*100:.1f}%. ĐÓNG BĂNG toàn bộ hoạt động mua mới."
    elif regime_info.get("freeze_quant", False) and book == "QUANT":
        cro_verdict = "VETO"
        cro_reason = f"CRO VETO [MARKET REGIME]: Thị trường trong trạng thái Downtrend/Risk-Off (Độ rộng {regime_info.get('breadth_ma20_pct', 0)}% > MA20). ĐÓNG BĂNG 100% vị thế mở mới Sổ QUANT."
    elif liq_stats.get("is_currently_floor_locked", False):
        cro_verdict = "VETO"
        cro_reason = f"CRO VETO [FLOOR-LOCK SHOCK]: Mã {t} đang trong trạng thái KẸT SÀN / TRẮNG BÊN MUA (Dư bán sàn, bên mua cạn kiệt). Tuyệt đối cấm giải ngân bắt dao rơi."
    elif liq_stats.get("is_floor_risk_high", False):
        cro_verdict = "VETO"
        cro_reason = f"CRO VETO [LIQUIDITY FRAGILITY]: Mã {t} có lịch sử kẹt sàn liên tiếp (Điểm rủi ro thanh khoản {liq_stats.get('liquidity_stress_score')}/100, từng kẹt sàn {liq_stats.get('max_consecutive_floor_days')} phiên liên tiếp). Nguy cơ không thể thoát hàng khi thị trường sụp đổ."
    elif not is_liquid:
        cro_verdict = "VETO"
        cro_reason = f"CRO VETO [LIQUIDITY DEFICIT]: Thanh khoản 20 phiên của {t} chỉ đạt {adtv_billion:.1f} Tỷ VND (Yêu cầu >= {settings.MIN_ADTV_VND/1e9:.0f} Tỷ VND, ADV >= {settings.MIN_ADV_SHARES:,} CP). Nguy cơ kẹt hàng khi thị trường bán tháo."
    elif jev_risk.value > 0.70:
        cro_verdict = "VETO"
        cro_reason = f"CRO VETO [JEV RISK > 0.70]: Điểm rủi ro thực thi {jev_risk.value:.2f} vượt trần an toàn. {jev_risk.reasoning}"
    elif target_vol == 0 or (curr_holding_val >= max_capital):
        cro_verdict = "VETO"
        cro_reason = f"CRO VETO [CONCENTRATION LIMIT]: Danh mục đã nắm giữ {curr_holding_vol:,} CP {t} ({curr_holding_val:,.0f} VND), đạt trần tỷ trọng cho phép ({max_pct*100:.0f}% NAV)."
    elif book == "CORE" and (fa_score < 60.0 or fa_res.get("has_critical_flags", False)):
        cro_verdict = "VETO"
        cro_reason = f"CRO VETO [FA QUALITY]: Mã {t} không đủ chuẩn giải ngân sổ CORE (FA Score {fa_score} < 60 hoặc có cờ đỏ BCTC trọng yếu)."
    elif book == "QUANT" and ml_score < 0.35:
        cro_verdict = "VETO"
        cro_reason = f"CRO VETO [ML MOMENTUM]: Xung lượng định lượng ML Score {ml_score:.4f} quá yếu (< 0.35)."
    elif liq_stats.get("is_near_floor", False):
        cro_verdict = "CAUTION"
        target_vol = int(target_vol * 0.50 // 100) * 100
        cro_reason = f"CRO CẢNH BÁO [NEAR-FLOOR RISK]: Thị giá {t} đang tiệm cận sát giá sàn (< 1.5%). Áp dụng Haircut giảm 50% khối lượng xuống {target_vol:,} CP."
    elif red_flags:
        cro_verdict = "CAUTION"
        target_vol = int(target_vol * 0.70 // 100) * 100
        cro_reason = f"CRO CẢNH BÁO [RED FLAGS]: Phát hiện cảnh báo BCTC. Giảm 30% quy mô vị thế xuống {target_vol:,} CP."
    elif liquidity_adjusted:
        cro_verdict = "APPROVED"
        cro_reason = f"CRO PHÊ DUYỆT [LIQUIDITY CAPPED]: Khối lượng được giới hạn ở mức 2.0% ADV ({target_vol:,} CP, {adtv_billion:.1f} Tỷ/phiên) để chống trượt giá. Stop-loss: -{stop_loss_pct*100:.0f}%."
    else:
        cro_verdict = "APPROVED"
        cro_reason = f"CRO PHÊ DUYỆT: Vị thế an toàn trong hạn mức ({max_pct*100:.0f}% NAV). Thanh khoản {adtv_billion:.1f} Tỷ/phiên. Stop-loss: -{stop_loss_pct*100:.0f}%."

    print(f"\n6. 🛡️ Chief Risk Officer (CRO):")
    print(f"   • Sổ phân bổ: [{book}] | Hạn mức: {max_pct*100:.0f}% NAV ({max_capital:,.0f} VND)")
    print(f"   • Thanh khoản 20 phiên: ADV {adv_20:,.0f} CP | ADTV: {adtv_billion:.1f} Tỷ VND (Đạt chuẩn: {is_liquid})")
    print(f"   • Khối lượng đề xuất: {target_vol:,} CP | Stop-Loss: {stop_loss_price:,.2f} (-{stop_loss_pct*100:.0f}%)")
    print(f"   • Jev Execution Risk: {jev_risk.value:.2f}/1.00 (Latency: {jev_risk.latency_ms:.2f}ms) - Phán quyết: [{cro_verdict}]")
    print(f"   • PHÁN QUYẾT: [{cro_verdict}] - {cro_reason}")

    # 8. Agent 7: Chief Investment Officer (CIO Decision) có bọc Harness Guardrail
    now_ts = date.today().strftime("%Y%m%d%H%M%S")
    memo_id = f"MEMO-{now_ts}-{t}"

    if cro_verdict in ("APPROVED", "CAUTION"):
        try:
            cio_decision = f"CIO PHÊ DUYỆT ĐỀ XUẤT: Triệu tập thành công, mở lệnh MUA {target_vol:,} CP {t} trên Sổ {book}."
            order_id = guardrail.create_verified_proposed_order(
                ticker=t,
                action="BUY",
                proposed_price=latest_close,
                proposed_volume=target_vol,
                memo_id=memo_id,
                notes=f"Đề xuất từ Ủy Ban Đầu Tư AI ({book}) | Jev Risk: {jev_risk.value:.2f}",
                strategy_book=book
            )
            memo_status = "PROPOSED"
        except GuardrailVetoException as gve:
            cro_verdict = "VETO"
            cio_decision = f"CIO BÁC BỎ THEO GUARDRAIL VETO: {gve}"
            order_id = None
            memo_status = "REJECTED"
    else:
        cio_decision = f"CIO BÁC BỎ THEO PHÁN QUYẾT CRO: Không mở vị thế cho mã {t} tại thời điểm này."
        order_id = None
        memo_status = "REJECTED"

    print(f"\n7. 👑 Chief Investment Officer (CIO):")
    print(f"   • {cio_decision}")
    if order_id:
        print(f"   • Mã lệnh đề xuất (Harness Verified): {order_id}")

    # Đóng gói Telemetry System 1
    jev_telemetry = {
        "triage": triage_noul.to_dict(),
        "route": route_choice.to_dict(),
        "risk_score": jev_risk.to_dict(),
        "system_1_latency_ms": round(triage_noul.latency_ms + route_choice.latency_ms + jev_risk.latency_ms, 2)
    }

    # Lưu biên bản phiên họp vào Database
    memo_data = {
        "memo_id": memo_id,
        "ticker": t,
        "strategy_book": book,
        "trade_date": date.today().strftime("%Y-%m-%d"),
        "action": "BUY",
        "target_price": resistance_price,
        "stop_loss_price": stop_loss_price,
        "target_volume": target_vol,
        "macro_view": macro_view,
        "fa_summary": fa_summary,
        "ta_ml_summary": ta_ml_summary,
        "bull_arguments": bull_arguments,
        "bear_arguments": bear_arguments,
        "cro_verdict": cro_verdict,
        "cro_position_size": target_vol,
        "cio_decision": cio_decision,
        "status": memo_status,
        "jev_telemetry": jev_telemetry
    }
    db.save_decision_memo(memo_data)
    memo_data["order_id"] = order_id
    print(f"\n💾 Đã lưu biên bản họp Ủy Ban Đầu Tư ID: [{memo_id}] (Jev Telemetry gắn kèm)")
    return memo_data

def run_workflow_eod():
    """Chạy Workflow 04: Chốt sổ Kế toán cuối ngày (Mark-to-Market)"""
    print_banner()
    print("🌙 BẮT ĐẦU WORKFLOW 04: CHỐT SỔ KẾ TOÁN NAV NGÀY...")
    db = DatabaseManager()
    parquet_mgr = ParquetMarketDataManager()
    
    prices = parquet_mgr.get_latest_close_prices()
    today_str = date.today().strftime("%Y-%m-%d")
    
    res = db.close_daily_nav(
        trade_date=today_str,
        current_prices=prices,
        notes="Chốt sổ tự động cuối ngày qua main.py"
    )
    
    print(f"✅ ĐÃ CHỐT SỔ NAV NGÀY [{today_str}]:")
    print(f"   • Tổng Tài sản Ròng (NAV): {res['total_nav']:,.0f} VND")
    print(f"   • NAV Khả dụng (Liquid):  {res.get('liquid_nav', res['total_nav']):,.0f} VND")
    print(f"   • Tiền mặt:               {res['cash_balance']:,.0f} VND")
    print(f"   • Cổ phiếu:               {res['stock_value']:,.0f} VND")
    if res.get('frozen_assets_value', 0) > 0 or res.get('provision_loss', 0) > 0:
        print(f"   • Tài sản Đóng băng:      {res.get('frozen_assets_value', 0):,.0f} VND (Dự phòng: {res.get('provision_loss', 0):,.0f} VND)")
    print(f"   • Biến động ngày:         {res['daily_pnl']:+,.0f} VND ({res['daily_pnl_pct']:+.2f}%)")
    print(f"   • Lãi tạm tính:           {res['unrealized_pnl']:+,.0f} VND")

def run_wfa_cli(ticker: str = "HPG", n_splits: int = 4, window_type: str = "rolling"):
    """Thực thi Walk-Forward Analysis (WFA) trực tiếp từ dòng lệnh CLI"""
    print_banner()
    t = ticker.upper()
    print(f"🔬 BẮT ĐẦU WALK-FORWARD ANALYSIS (WFA) CHO MÃ: [{t}]")
    print(f"   • Số bước trượt: {n_splits} folds | Chế độ: {window_type.upper()}")

    from core.backtest.runner import BacktestRunner
    from core.backtest.strategy_template import VSAMomentumStrategy
    from core.backtest.report_adapter import BacktestReportAdapter

    runner = BacktestRunner()
    wfa_res = runner.run_walk_forward_analysis(
        strategy_class=VSAMomentumStrategy,
        tickers=t,
        days=1250,
        n_splits=n_splits,
        window_type=window_type,
        strategy_name=f"VSA Momentum ({t})"
    )

    summary = wfa_res["summary"]
    print(f"\n🏆 KẾT QUẢ WALK-FORWARD ANALYSIS ({wfa_res['n_splits']} FOLDS):")
    print(f"   • Phán quyết:             [{wfa_res['verdict']}]")
    print(f"   • WFE Sharpe:             {summary['wfe_sharpe_pct']:.1f}% (Hệ số bảo toàn hiệu suất OOS)")
    print(f"   • Sharpe OOS Trung bình:  {summary['avg_oos_sharpe']:.2f} (Sharpe IS TB: {summary['avg_is_sharpe']:.2f})")
    print(f"   • CAGR OOS Trung bình:    {summary['avg_oos_cagr_pct']:+.2f}%/năm")
    print(f"   • Max Drawdown OOS TB:    {summary['avg_oos_mdd_pct']:.2f}%")
    print(f"   • Số Folds OOS Có Lãi:    {summary['profitable_folds']}/{summary['total_folds']} ({summary['profitable_folds_pct']:.1f}%)")
    print(f"   • Nhận định:              {wfa_res['assessment']}")

    print("\n📋 CHI TIẾT TỪNG BƯỚC TRƯỢT (FOLDS):")
    for f in wfa_res["folds"]:
        is_m = f["in_sample"]
        oos_m = f["out_of_sample"]
        print(f"   • Fold #{f['fold']}: IS Sharpe {is_m['sharpe']:.2f} -> OOS Sharpe {oos_m['sharpe']:.2f} (Bảo toàn: {f['sharpe_retention_pct']:.1f}%, MDD: {oos_m['mdd_pct']:.1f}%, Win: {oos_m['win_rate_pct']:.1f}%)")

    # Xuất báo cáo Markdown
    out_dir = settings.BASE_DIR / ".agent" / "journals"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / f"wfa_report_{t.lower()}_{window_type}_{date.today().strftime('%Y%m%d')}.md"
    BacktestReportAdapter.generate_walk_forward_markdown_report(wfa_res, output_path=report_file)
    print(f"\n📄 Đã lưu báo cáo chi tiết: {report_file}")

def main():
    parser = argparse.ArgumentParser(description="Bộ Điều Phối Trung Tâm Quỹ Đầu Tư AI (Antigravity Orchestrator)")
    parser.add_argument("--status", action="store_true", help="Xem báo cáo tổng quan tình trạng Quỹ")
    parser.add_argument("--workflow", choices=["morning", "debate", "eod", "triage"], help="Kích hoạt một quy trình làm việc SOP (morning, debate, eod, triage)")
    parser.add_argument("--ticker", default="HPG", help="Mã cổ phiếu dùng cho workflow debate/triage/wfa (mặc định HPG)")
    parser.add_argument("--book", choices=["CORE", "QUANT"], default="QUANT", help="Sổ chiến lược: CORE (Fundamental) hoặc QUANT (Trading)")
    parser.add_argument("--optimize", nargs="?", const="vsa-momentum", help="Kích hoạt Động cơ Tự học & Tiến hóa chiến lược (ví dụ: --optimize vsa-momentum)")
    parser.add_argument("--wfa", action="store_true", help="Chạy Walk-Forward Analysis (WFA) kiểm định độ bền vững trượt của chiến lược")
    parser.add_argument("--splits", type=int, default=4, help="Số folds bước trượt cho WFA (mặc định: 4)")
    parser.add_argument("--window-type", choices=["rolling", "expanding"], default="rolling", help="Chế độ cửa sổ WFA: rolling hoặc expanding (mặc định: rolling)")
    parser.add_argument("--serve-dashboard", action="store_true", help="Khởi chạy Web Dashboard server (cổng 8000)")
    
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.wfa:
        run_wfa_cli(ticker=args.ticker, n_splits=args.splits, window_type=args.window_type)
    elif args.optimize:
        from core.backtest.strategy_optimizer import StrategyOptimizerEngine
        print_banner()
        engine = StrategyOptimizerEngine()
        engine.auto_heal_vsa_strategy(ticker=args.ticker)
    elif args.workflow == "morning":
        run_workflow_morning()
    elif args.workflow == "debate":
        run_workflow_debate(args.ticker, strategy_book=args.book)
    elif args.workflow == "triage":
        run_workflow_triage(args.ticker)
    elif args.workflow == "eod":
        run_workflow_eod()
    elif args.serve_dashboard:
        import uvicorn
        print_banner()
        print("🌐 Đang khởi chạy Web Dashboard tại http://localhost:8000 ...")
        uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=False)
    else:
        show_status()

if __name__ == "__main__":
    main()

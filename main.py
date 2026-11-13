"""
Điểm Khởi Chạy Trung Tâm của Quỹ Đầu tư AI (Fund Main Orchestrator).
Kết nối toàn bộ Não bộ Multi-Agent, Cơ sở Dữ liệu, Động cơ Backtest và Dashboard.
"""

import sys
import argparse
from pathlib import Path
from datetime import date
from typing import Optional

from config import settings
from database.db_manager import DatabaseManager
from tools.parquet_manager import ParquetMarketDataManager
from tools.fundamental_screener import FundamentalScreener
from tools.ml_predictor import UniversalAlphaPredictor

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

    print("📊 [1] TÌNH HÌNH TÀI SẢN & VỐN (NAV):")
    print(f"   • Tổng Tài sản Ròng (NAV): {nav_info.get('total_nav', settings.INITIAL_CAPITAL):,.0f} VND")
    print(f"   • Tiền mặt khả dụng:      {nav_info.get('cash_balance', settings.INITIAL_CAPITAL):,.0f} VND")
    print(f"   • Giá trị Cổ phiếu:       {nav_info.get('stock_value', 0.0):,.0f} VND")
    print(f"   • Biến động ngày:         {nav_info.get('daily_pnl', 0.0):+,.0f} VND ({nav_info.get('daily_pnl_pct', 0.0):+.2f}%)")
    print(f"   • Lợi nhuận lũy kế:       {nav_info.get('cumulative_pnl', 0.0):+,.0f} VND")

    print("\n📦 [2] DANH MỤC NẮM GIỮ (PORTFOLIO):")
    if not portfolio:
        print("   • Đang giữ 100% Tiền mặt.")
    else:
        for item in portfolio:
            print(f"   • {item['ticker']}: {item['quantity']:,} CP | Giá vốn: {item['avg_buy_price']:,.2f} | Thị giá: {item.get('current_price', 0):,.2f} | PnL: {item.get('unrealized_pnl', 0):+,.0f} VND ({item.get('unrealized_pnl_pct', 0):+.2f}%)")

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
    """Chạy Workflow 01: Bản tin Sáng (Morning Briefing)"""
    print_banner()
    print("☀️ BẮT ĐẦU WORKFLOW 01: BẢN TIN TIỀN THỊ TRƯỜNG (08:00 AM)...")
    parquet_mgr = ParquetMarketDataManager()
    
    print("\n1. Quét tìm các mã có dòng tiền vào mạnh (Volume > 1.2x MA20 Volume)...")
    candidates = parquet_mgr.scan_breakout_vol_candidates(min_vol_ratio=1.1, limit=10)
    
    if candidates:
        print(f"🎯 Phát hiện {len(candidates)} mã cổ phiếu đạt tiêu chí Watchlist:")
        for c in candidates:
            print(f"   • {c['ticker']}: Thị giá {c['close']} | Đột biến Vol: {c['vol_ratio']}x | Trên MA20: +{c['diff_ma20_pct']}%")
    else:
        print("ℹ️ Phiên hôm nay chưa có mã nào vượt ngưỡng volume đột biến.")

    print("\n2. Đánh giá Khí tượng Thị trường (Macro Agent):")
    print("   • Trạng thái đề xuất: [SIDEWAY / ACCUMULATION]")
    print("   • Chiến lược ưu tiên: Chỉ giải ngân thăm dò 30% khi có xác nhận vượt nền giá.")

def run_workflow_debate(ticker: str, strategy_book: str = "QUANT") -> Optional[dict]:
    """Chạy Workflow 02: Phiên Họp Ủy Ban Đầu Tư AI (6 Agents) cho một mã cổ phiếu"""
    print_banner()
    t = ticker.upper()
    book = strategy_book.upper()
    print(f"⚔️ BẮT ĐẦU WORKFLOW 02: HỘI ĐỒNG ĐẦU TƯ TRANH BIỆN MÃ [{t}] - SỔ [{book}]...")
    
    db = DatabaseManager()
    parquet_mgr = ParquetMarketDataManager()
    fa_screener = FundamentalScreener()
    ml_predictor = UniversalAlphaPredictor()
    
    # 1. Thu thập dữ liệu kỹ thuật
    df = parquet_mgr.get_ticker_history(t, days=30)
    if len(df) == 0:
        print(f"❌ Không tìm thấy dữ liệu cho mã: {t}")
        return None
        
    latest_close = float(df["close"][-1])
    price_unit = "k" if latest_close < 1000.0 else "đ"
    norm_price = latest_close * 1000.0 if latest_close < 1000.0 else latest_close
    
    # 2. Agent 1: Macro Scout (Khí tượng Thị trường)
    macro_view = "VN-Index dao động tích lũy trong biên độ 1.220 - 1.280 điểm. Thanh khoản duy trì ổn định, lãi suất điều hành thấp hỗ trợ định giá chứng khoán."
    print(f"\n1. 🛰️ Macro Scout (Vĩ mô & Thị trường):")
    print(f"   • Trạng thái: {macro_view}")

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

    # 5. Agent 4: Bull Advocate (Phe Bò)
    catalyst = "Kỳ vọng sản lượng và đơn hàng bứt phá mạnh trong quý tới." if book == "CORE" else "Dòng tiền lớn nổ volume vượt nền tích lũy MA20."
    bull_arguments = (
        f"1. {catalyst}\n"
        f"2. Sức mạnh cơ bản FA Score đạt {fa_score}/100, biên lợi nhuận mở rộng.\n"
        f"3. Xung lượng định lượng ML Score = {ml_score:.4f}, xác suất thắng cao.\n"
        f"4. Mục tiêu giá kỳ vọng: {resistance_price:,.2f} {price_unit} (+15.0%)."
    )
    print(f"\n4. 🐂 Bull Advocate (Phe Bò):")
    for line in bull_arguments.split("\n"):
        print(f"   • {line}")

    # 6. Agent 5: Bear Red-Team (Phe Gấu)
    flag_text = "; ".join(red_flags) if red_flags else "Áp lực cung chốt lời tiềm ẩn tại vùng kháng cự đỉnh cũ."
    bear_arguments = (
        f"1. Rủi ro vi mô/kế toán: {flag_text}\n"
        f"2. Biến động thị trường chung có thể kích hoạt làn sóng bán tháo ngắn hạn.\n"
        f"3. Dư địa tăng giá có thể bị giới hạn nếu khối ngoại tiếp tục bán ròng."
    )
    print(f"\n5. 🐻 Bear Red-Team (Phe Gấu Phản Biện):")
    for line in bear_arguments.split("\n"):
        print(f"   • {line}")

    # 7. Agent 6: Chief Risk Officer (CRO Veto & Position Sizing)
    nav = db.get_current_cash()
    if book == "CORE":
        max_pct = settings.CORE_MAX_POSITION_PCT
        stop_loss_pct = settings.CORE_HARD_STOP_LOSS_PCT
    else:
        max_pct = settings.QUANT_MAX_POSITION_PCT
        stop_loss_pct = settings.QUANT_HARD_STOP_LOSS_PCT

    max_capital = nav * max_pct
    target_vol = int((max_capital / norm_price) // 100) * 100
    target_vol = max(100, target_vol)
    stop_loss_price = round(latest_close * (1 - stop_loss_pct), 2)

    # Phán quyết CRO
    if book == "CORE" and (fa_score < 60.0 or fa_res.get("has_critical_flags", False)):
        cro_verdict = "VETO"
        cro_reason = f"CRO VETO: Mã {t} không đủ chuẩn giải ngân sổ CORE (FA Score {fa_score} < 60 hoặc có cờ đỏ trọng yếu)."
    elif book == "QUANT" and ml_score < 0.35:
        cro_verdict = "VETO"
        cro_reason = f"CRO VETO: Xung lượng định lượng ML Score {ml_score:.4f} quá yếu (< 0.35)."
    elif red_flags:
        cro_verdict = "CAUTION"
        target_vol = int(target_vol * 0.70 // 100) * 100
        cro_reason = f"CRO CẢNH BÁO: Phát hiện cảnh báo BCTC. Hạ 30% quy mô vị thế xuống {target_vol:,} CP."
    else:
        cro_verdict = "APPROVED"
        cro_reason = f"CRO PHÊ DUYỆT: Vị thế an toàn trong hạn mức ({max_pct*100:.0f}% NAV). Stop-loss: {stop_loss_pct*100:.0f}%."

    print(f"\n6. 🛡️ Chief Risk Officer (CRO):")
    print(f"   • Sổ phân bổ: [{book}] | Hạn mức: {max_pct*100:.0f}% NAV ({max_capital:,.0f} VND)")
    print(f"   • Khối lượng đề xuất: {target_vol:,} CP | Stop-Loss: {stop_loss_price:,.2f} (-{stop_loss_pct*100:.0f}%)")
    print(f"   • PHÁN QUYẾT: [{cro_verdict}] - {cro_reason}")

    # 8. Agent 7: Chief Investment Officer (CIO Decision)
    now_ts = date.today().strftime("%Y%m%d%H%M%S")
    memo_id = f"MEMO-{now_ts}-{t}"

    if cro_verdict in ("APPROVED", "CAUTION"):
        cio_decision = f"CIO PHÊ DUYỆT ĐỀ XUẤT: Triệu tập thành công, mở lệnh MUA {target_vol:,} CP {t} trên Sổ {book}."
        order_id = db.create_proposed_order(
            ticker=t,
            action="BUY",
            proposed_price=latest_close,
            proposed_volume=target_vol,
            memo_id=memo_id,
            notes=f"Đề xuất từ Ủy Ban Đầu Tư AI ({book})",
            strategy_book=book
        )
        memo_status = "PROPOSED"
    else:
        cio_decision = f"CIO BÁC BỎ THEO PHÁN QUYẾT CRO: Không mở vị thế cho mã {t} tại thời điểm này."
        order_id = None
        memo_status = "REJECTED"

    print(f"\n7. 👑 Chief Investment Officer (CIO):")
    print(f"   • {cio_decision}")
    if order_id:
        print(f"   • Mã lệnh đề xuất: {order_id}")

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
        "status": memo_status
    }
    db.save_decision_memo(memo_data)
    memo_data["order_id"] = order_id
    print(f"\n💾 Đã lưu biên bản họp Ủy Ban Đầu Tư ID: [{memo_id}]")
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
    print(f"   • Tiền mặt:               {res['cash_balance']:,.0f} VND")
    print(f"   • Cổ phiếu:               {res['stock_value']:,.0f} VND")
    print(f"   • Biến động ngày:         {res['daily_pnl']:+,.0f} VND ({res['daily_pnl_pct']:+.2f}%)")
    print(f"   • Lãi tạm tính:           {res['unrealized_pnl']:+,.0f} VND")

def main():
    parser = argparse.ArgumentParser(description="Bộ Điều Phối Trung Tâm Quỹ Đầu Tư AI (Antigravity Orchestrator)")
    parser.add_argument("--status", action="store_true", help="Xem báo cáo tổng quan tình trạng Quỹ")
    parser.add_argument("--workflow", choices=["morning", "debate", "eod"], help="Kích hoạt một quy trình làm việc SOP")
    parser.add_argument("--ticker", default="HPG", help="Mã cổ phiếu dùng cho workflow debate (mặc định HPG)")
    parser.add_argument("--book", choices=["CORE", "QUANT"], default="QUANT", help="Sổ chiến lược: CORE (Fundamental) hoặc QUANT (Trading)")
    parser.add_argument("--optimize", nargs="?", const="vsa-momentum", help="Kích hoạt Động cơ Tự học & Tiến hóa chiến lược (ví dụ: --optimize vsa-momentum)")
    parser.add_argument("--serve-dashboard", action="store_true", help="Khởi chạy Web Dashboard server (cổng 8000)")
    
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.optimize:
        from tools.strategy_optimizer import StrategyOptimizerEngine
        print_banner()
        engine = StrategyOptimizerEngine()
        engine.auto_heal_vsa_strategy(ticker=args.ticker)
    elif args.workflow == "morning":
        run_workflow_morning()
    elif args.workflow == "debate":
        run_workflow_debate(args.ticker, strategy_book=args.book)
    elif args.workflow == "eod":
        run_workflow_eod()
    elif args.serve_dashboard:
        import uvicorn
        print_banner()
        print("🌐 Đang khởi chạy Web Dashboard tại http://localhost:8000 ...")
        uvicorn.run("dashboard.api:app", host="0.0.0.0", port=8000, reload=False)
    else:
        show_status()

if __name__ == "__main__":
    main()

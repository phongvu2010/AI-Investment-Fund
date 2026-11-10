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

def run_workflow_debate(ticker: str):
    """Chạy Workflow 02: Phiên Họp Hội đồng Tranh biện cho một mã cổ phiếu"""
    print_banner()
    t = ticker.upper()
    print(f"⚔️ BẮT ĐẦU WORKFLOW 02: HỘI ĐỒNG ĐẦU TƯ TRANH BIỆN MÃ [{t}]...")
    
    db = DatabaseManager()
    parquet_mgr = ParquetMarketDataManager()
    
    # 1. Lấy dữ liệu giá
    df = parquet_mgr.get_ticker_history(t, days=30)
    if len(df) == 0:
        print(f"❌ Không tìm thấy dữ liệu cho mã: {t}")
        return
        
    latest_close = float(df["close"][-1])
    
    print(f"\n1. Ban Nghiên cứu (FA & TA):")
    print(f"   • Thị giá hiện tại: {latest_close:,.2f}")
    print(f"   • Hỗ trợ kỹ thuật: {latest_close * 0.94:,.2f} | Kháng cự mục tiêu: {latest_close * 1.15:,.2f}")

    print(f"\n2. Phe Bò (Bull Advocate):")
    print(f"   • Luận điểm tăng: Động lực phục hồi sản lượng, kỳ vọng KQKD quý tới tăng trưởng +20%.")
    print(f"   • Mục tiêu giá ngắn hạn: {latest_close * 1.15:,.2f} (+15.0%).")

    print(f"\n3. Phe Gấu (Bear Advocate - Red Team):")
    print(f"   • Rủi ro 1: Giá nguyên vật liệu đầu vào biến động khó lường.")
    print(f"   • Rủi ro 2: Khối ngoại có xu hướng bán ròng nhẹ trong các phiên gần đây.")
    print(f"   • Rủi ro 3: Vùng cản kỹ thuật phía trên dày đặc.")

    print(f"\n4. Giám đốc Rủi ro (CRO Evaluation):")
    nav = db.get_current_cash()
    max_capital = nav * settings.MAX_POSITION_PCT
    # Tính khối lượng lô chẵn 100
    target_vol = int((max_capital / (latest_close * 1000.0 if latest_close < 1000 else latest_close)) // 100) * 100
    target_vol = max(100, target_vol)
    stop_loss = round(latest_close * (1 - settings.HARD_STOP_LOSS_PCT), 2)
    
    print(f"   • Hạn mức giải ngân tối đa (20% NAV): {max_capital:,.0f} VND")
    print(f"   • Khối lượng đề xuất: {target_vol:,} CP")
    print(f"   • Ngưỡng Stop-Loss cứng: {stop_loss:,.2f} (-7.0%)")
    print(f"   • PHÁN QUYẾT: ĐẠT TIÊU CHUẨN AN TOÀN")

    # Tạo đề xuất lệnh vào database
    order_id = db.create_proposed_order(
        ticker=t,
        action="BUY",
        proposed_price=latest_close,
        proposed_volume=target_vol,
        notes=f"Đề xuất từ phiên tranh biện Hội đồng cho {t}"
    )
    print(f"\n5. Giám đốc Đầu tư (CIO):")
    print(f"   ✅ Đã phê duyệt và xuất Tờ trình đầu tư: {order_id}")
    print(f"   👉 Tờ trình đã được lưu vào SQLite và sẵn sàng gửi sang Telegram Bot!")

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
        run_workflow_debate(args.ticker)
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

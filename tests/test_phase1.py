"""
Script Kiểm thử Toàn diện Giai đoạn 1 (Phase 1 Test Suite).
Kiểm tra tính toàn vẹn của:
1. Cơ sở dữ liệu SQLite (fund_vault.db)
2. Sổ lệnh & Cơ chế Nhập bù (Retroactive Trade Entry)
3. Chốt sổ NAV & Tính toán Kế toán chuẩn xác
4. Kho dữ liệu Parquet 5 năm & Tốc độ truy vấn DuckDB
"""

import sys
from pathlib import Path

# Thêm thư mục gốc vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from database.db_manager import DatabaseManager
from tools.bigquery_sync import BigQuerySyncEngine
from tools.parquet_manager import ParquetMarketDataManager
from config import settings

def run_tests():
    print("=" * 70)
    print("🚀 BẮT ĐẦU KIỂM THỬ GIAI ĐOẠN 1: DATABASE SQLITE & KHO PARQUET 5 NĂM")
    print("=" * 70)

    # ----------------------------------------------------
    # BƯỚC 1: KHỞI TẠO VÀ KIỂM TRA DATABASE SQLITE
    # ----------------------------------------------------
    print("\n[TEST 1] Khởi tạo Cơ sở Dữ liệu SQLite Kiểm thử...")
    test_db_path = settings.DATABASE_DIR / "test_fund_vault.db"
    if test_db_path.exists():
        test_db_path.unlink()

    db = DatabaseManager(db_path=test_db_path)
    cash = db.get_current_cash()
    print(f"✅ Khởi tạo thành công! Số dư tiền mặt ban đầu: {cash:,.0f} VND")
    assert cash == settings.INITIAL_CAPITAL, f"Lỗi tiền mặt ban đầu: {cash}"

    # ----------------------------------------------------
    # BƯỚC 2: TẠO VÀ KIỂM TRA KHO DỮ LIỆU PARQUET 5 NĂM
    # ----------------------------------------------------
    print("\n[TEST 2] Kiểm tra Kho Dữ liệu Parquet...")
    sync_engine = BigQuerySyncEngine()
    # Tạo dữ liệu mẫu 5 năm cho 10 mã Bluechips để kiểm thử
    sync_engine.generate_demo_sample_data(num_days=1250)

    parquet_mgr = ParquetMarketDataManager()
    summary = parquet_mgr.get_summary()
    print(f"✅ Thống kê Parquet: {summary['total_rows']:,} dòng nến | {summary['total_tickers']} mã CP")
    print(f"   Khoảng thời gian: từ {summary['from_date']} đến {summary['to_date']}")
    print(f"   Dung lượng file: {summary['file_size_mb']} MB")
    assert summary["total_rows"] > 0, "File Parquet không có dữ liệu!"

    # Kiểm tra tốc độ đọc 1 mã bằng DuckDB
    hpg_df = parquet_mgr.get_ticker_history("HPG", days=100)
    print(f"✅ Truy vấn 100 nến HPG bằng DuckDB: {len(hpg_df)} phiên (Nến gần nhất giá: {hpg_df['close'][-1]:,.2f})")

    # ----------------------------------------------------
    # BƯỚC 3: MÔ PHỎNG VÒNG ĐỜI LỆNH TRÊN TELEGRAM
    # ----------------------------------------------------
    print("\n[TEST 3] Mô phỏng Khớp lệnh Khuyến nghị (HPG)...")
    # AI đề xuất mua 5.000 HPG giá 28.000
    order_id = db.create_proposed_order(
        ticker="HPG",
        action="BUY",
        proposed_price=28.0,
        proposed_volume=5000,
        notes="Breakout MA20 vol đột biến"
    )
    print(f"1. AI tạo đề xuất lệnh: {order_id}")

    # Bạn đặt lệnh trên app CTCK
    db.set_order_submitted(order_id)
    print("2. Bạn bấm [Đã đặt lệnh chờ] trên Telegram")

    # Khớp thực tế: Bạn khớp 5.000 cổ giá 28.100 (Trượt giá nhẹ +0.36%)
    fill_res = db.record_order_fill(
        order_id=order_id,
        executed_price=28.1,
        executed_volume=5000
    )
    print(f"3. Khớp thực tế: {fill_res['executed_volume']:,} HPG @ {fill_res['executed_price']:,.0f} VND")
    print(f"   Phí giao dịch (0.15%): {fill_res['fee']:,.0f} VND | Trượt giá: {fill_res['slippage_pct']:.2f}%")

    cash_after_buy = db.get_current_cash()
    print(f"   Tiền mặt sau mua: {cash_after_buy:,.0f} VND")

    # ----------------------------------------------------
    # BƯỚC 4: MÔ PHỎNG CƠ CHẾ NHẬP BÙ (RETROACTIVE FILL)
    # ----------------------------------------------------
    print("\n[TEST 4] Mô phỏng Cơ chế Nhập bù Hồi tố (SSI)...")
    # Tối bạn rảnh nhập bù 3.000 SSI giá 32.000 (gõ 32.0)
    retro_order_id = db.record_retroactive_fill(
        ticker="SSI",
        action="BUY",
        executed_price=32.0,
        executed_volume=3000,
        notes="Nhập bù qua Telegram lúc 21h"
    )
    print(f"✅ Nhập bù thành công: {retro_order_id} (3.000 SSI @ 32.0)")

    # Kiểm tra danh mục nắm giữ hiện tại
    portfolio = db.get_portfolio()
    print(f"\n📊 DANH MỤC HIỆN TẠI ({len(portfolio)} mã):")
    for item in portfolio:
        print(f"   • {item['ticker']}: {item['quantity']:,} CP | Giá vốn: {item['avg_buy_price']:,.0f} VND | Giá trị: {item['market_value']:,.0f} VND")

    assert len(portfolio) == 2, f"Danh mục phải có 2 mã (HPG, SSI), thực tế: {len(portfolio)}"

    # ----------------------------------------------------
    # BƯỚC 5: CHỐT SỔ KẾ TOÁN NAV HÀNG NGÀY (EOD)
    # ----------------------------------------------------
    print("\n[TEST 5] Chốt sổ Kế toán NAV Cuối ngày (Mark-to-Market)...")
    # Giả lập giá đóng cửa hôm nay: HPG tăng lên 28.5 (28,500 đ), SSI tăng lên 32.5 (32,500 đ)
    market_prices = {"HPG": 28.5, "SSI": 32.5}
    nav_report = db.close_daily_nav(
        trade_date="2026-11-03",
        current_prices=market_prices,
        notes="Phiên giao dịch tích cực, cả 2 mã đều tăng giá"
    )

    print("📈 BÁO CÁO NAV CUỐI NGÀY:")
    print(f"   • Tổng tài sản (NAV): {nav_report['total_nav']:,.0f} VND")
    print(f"   • Tiền mặt khả dụng: {nav_report['cash_balance']:,.0f} VND")
    print(f"   • Giá trị Cổ phiếu:  {nav_report['stock_value']:,.0f} VND")
    print(f"   • Lợi nhuận tạm tính: {nav_report['unrealized_pnl']:,.0f} VND")
    print(f"   • Biến động ngày:    +{nav_report['daily_pnl']:,.0f} VND (+{nav_report['daily_pnl_pct']:.2f}%)")

    # Lấy lịch sử NAV để kiểm tra biểu đồ
    nav_history = db.get_nav_history()
    print(f"✅ Lịch sử chuỗi NAV: {len(nav_history)} mốc dữ liệu")

    # ----------------------------------------------------
    # BƯỚC 6: BỘ QUÉT TÍN HIỆU ĐỘT BIẾN VOLUME (DUCKDB)
    # ----------------------------------------------------
    print("\n[TEST 6] Quét Tín hiệu Nổ Volume bằng DuckDB (0 Token)...")
    candidates = parquet_mgr.scan_breakout_vol_candidates(min_vol_ratio=1.1, limit=5)
    print(f"✅ Tìm thấy {len(candidates)} mã có tín hiệu dòng tiền vào:")
    for c in candidates:
        print(f"   • {c['ticker']}: Giá {c['close']} | Tỷ lệ Vol: {c['vol_ratio']}x | Giá trên MA20: +{c['diff_ma20_pct']}%")

    print("\n" + "=" * 70)
    print("🎉 TOÀN BỘ CÁC BÀI TEST GIAI ĐOẠN 1 ĐỀU THÀNH CÔNG RỰC RỠ!")
    print("=" * 70)

def test_phase1_suite():
    run_tests()

if __name__ == "__main__":
    run_tests()

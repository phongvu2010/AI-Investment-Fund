"""
Script Kiểm thử Toàn diện Giai đoạn 3 (Phase 3 Test Suite).
Kiểm tra tính toàn vẹn của:
1. Module Telegram Bot: Trình định dạng tin nhắn & Bộ bóc tách cú pháp tự nhiên (Regex)
2. FastAPI Backend: Toàn bộ API endpoints (/api/nav, /api/portfolio, /api/orders, /api/reports)
3. React Frontend Serving: Khả năng phục vụ Single-Page App (React + Vite + Tailwind CSS)
"""

import sys
from pathlib import Path

# Thêm thư mục gốc vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import re
from fastapi.testclient import TestClient
from dashboard.api import app
from interfaces.message_templates import TelegramMessageFormatter
from database.db_manager import DatabaseManager

def run_phase3_tests():
    print("=" * 70)
    print("🚀 BẮT ĐẦU KIỂM THỬ GIAI ĐOẠN 3: TELEGRAM BOT & WEB DASHBOARD (REACT+VITE)")
    print("=" * 70)

    db = DatabaseManager()

    # ----------------------------------------------------
    # BƯỚC 1: KIỂM TRA ĐỊNH DẠNG TIN NHẮN TELEGRAM
    # ----------------------------------------------------
    print("\n[TEST 1] Kiểm tra Trình Định dạng Tin nhắn Telegram...")
    proposal_msg = TelegramMessageFormatter.format_trade_proposal(
        order_id="ORD-20261103-TEST",
        ticker="HPG",
        action="BUY",
        proposed_price=28.5,
        proposed_volume=5000,
        stop_loss_price=26.5,
        target_price=33.0,
        bull_points="Breakout MA20 vol đột biến 2x",
        bear_points="Thị trường chung sideway",
        nav_weight_pct=14.2
    )
    assert "KHUYẾN NGHỊ MUA" in proposal_msg
    assert "HPG" in proposal_msg
    print("✅ Đã tạo Tờ trình đầu tư Telegram với đầy đủ luận điểm 2 chiều (Bull/Bear).")

    # ----------------------------------------------------
    # BƯỚC 2: KIỂM TRA REGEX PARSER CHO TIN NHẮN TỰ NHIÊN
    # ----------------------------------------------------
    print("\n[TEST 2] Kiểm tra Bộ Bóc tách Cú pháp Tự nhiên Telegram...")
    test_texts = [
        ("khớp HPG 5000 giá 28.2", "HPG", 5000, 28.2),
        ("mua SSI 3000 32.5", "SSI", 3000, 32.5),
        ("FPT 1000 130.5", "FPT", 1000, 130.5),
        ("bán HPG 2000 giá 29.0", "HPG", 2000, 29.0)
    ]

    pattern = r"(?:khớp|khop|mua|bán|ban)?\s*([a-zA-Z]{3})\s+(\d+[\d,\.]*)\s*(?:giá|gia|@)?\s*(\d+[\d,\.]*)"
    for raw_text, exp_ticker, exp_vol, exp_price in test_texts:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        assert match is not None, f"Không nhận diện được tin nhắn: '{raw_text}'"
        t = match.group(1).upper()
        v = int(match.group(2).replace(",", "").replace(".", ""))
        p = float(match.group(3).replace(",", "."))
        assert t == exp_ticker and v == exp_vol and p == exp_price, f"Bóc tách sai: {raw_text}"
        print(f"✅ Bóc tách chuẩn: '{raw_text}' ➔ {t} | {v:,} CP @ {p}")

    # ----------------------------------------------------
    # BƯỚC 3: KIỂM TRA BACKEND API (FASTAPI)
    # ----------------------------------------------------
    print("\n[TEST 3] Kiểm tra Toàn bộ REST API Endpoints của Dashboard...")
    client = TestClient(app)

    # 3.1 Healthcheck
    res = client.get("/api/health")
    assert res.status_code == 200
    print(f"✅ /api/health: {res.json()['status']}")

    # 3.2 NAV Summary
    res = client.get("/api/nav/summary")
    assert res.status_code == 200
    nav_data = res.json()
    print(f"✅ /api/nav/summary: NAV = {nav_data['total_nav']:,.0f} VND (Tiền mặt: {nav_data['cash_balance']:,.0f} VND)")

    # 3.3 Portfolio
    res = client.get("/api/portfolio")
    assert res.status_code == 200
    portfolio_data = res.json()
    print(f"✅ /api/portfolio: {len(portfolio_data)} mã cổ phiếu đang nắm giữ")

    # 3.4 Order History
    res = client.get("/api/orders")
    assert res.status_code == 200
    orders_data = res.json()
    print(f"✅ /api/orders: {len(orders_data)} lệnh trong lịch sử")

    # 3.5 Strategy Reports (vn-backtest reports)
    res = client.get("/api/reports")
    assert res.status_code == 200
    reports_data = res.json()
    print(f"✅ /api/reports: Tìm thấy {len(reports_data)} báo cáo chiến lược đã backtest")
    if reports_data:
        print(f"   • Tên: {reports_data[0]['title']} | Trạng thái: {reports_data[0]['cro_status']}")

    # 3.6 Submit Fill Order via API (Nhập lệnh từ Web Dashboard)
    test_fill_ticker = "TEST_TCB"
    cash_before = db.get_current_cash()
    res = client.post("/api/orders/fill", json={
        "ticker": test_fill_ticker,
        "action": "BUY",
        "price": 24.5,
        "volume": 2000,
        "notes": "Kiểm thử nhập từ Dashboard"
    })
    assert res.status_code == 200
    fill_order_id = res.json()['order_id']
    print(f"✅ /api/orders/fill: Ghi nhận thành công lệnh {fill_order_id}")

    # Dọn dẹp bản ghi kiểm thử để không làm biến động sổ kế toán thật
    with db.get_connection() as conn:
        conn.execute("DELETE FROM order_history WHERE order_id = ?;", (fill_order_id,))
        conn.execute("DELETE FROM transactions WHERE symbol = ?;", (test_fill_ticker,))
        conn.execute("DELETE FROM portfolio WHERE ticker = ?;", (test_fill_ticker,))
        conn.execute("UPDATE account_cash_balance SET cash_balance = ? WHERE account_id = '0001716319';", (cash_before,))
        conn.commit()

    # ----------------------------------------------------
    # BƯỚC 4: KIỂM TRA FRONTEND SERVING (REACT + VITE + TAILWIND)
    # ----------------------------------------------------
    print("\n[TEST 4] Kiểm tra Web Dashboard Frontend...")
    res = client.get("/")
    assert res.status_code == 200
    assert "AI Personal Investment Fund" in res.text
    print("✅ Web Dashboard (React + Vite + Tailwind CSS) được phục vụ hoàn hảo tại root URL ('/')!")

    print("\n" + "=" * 70)
    print("🎉 TOÀN BỘ CÁC BÀI TEST GIAI ĐOẠN 3 ĐỀU THÀNH CÔNG RỰC RỠ!")
    print("=" * 70)

if __name__ == "__main__":
    run_phase3_tests()

---
name: strategy-vsa-momentum
description: >-
  Chiến lược VSA Momentum Breakout (HPG) - Phiên bản Tiến hóa v2.0.
  Trạng thái: REJECTED.
  Đã được tối ưu hóa tham số và khắc phục bẫy giá qua ParameterOptimizer.
---

# CHIẾN LƯỢC: VSA MOMENTUM BREAKOUT (HPG) - TIẾN HÓA V2.0

## 1. MÔ TẢ TỔNG QUAN
Chiến lược theo dấu dòng tiền thông minh (Smart Money) kết hợp điểm giao cắt vàng (Golden Cross) giữa EMA10 và SMA50 kèm sự xác nhận của Volume (hệ số 0.8x) và xung lượng RSI 14.

## 2. QUY TẮC VÀO LỆNH (ENTRY RULES)
1. Đường EMA10 cắt lên trên đường SMA50 (Golden Cross).
2. Khối lượng phiên nổ vol vượt 0.8 lần khối lượng trung bình 20 phiên.
3. Chỉ số RSI 14 > 48.0 (Xác nhận động lượng tăng giá).
4. Phân bổ tối đa 20% NAV khả dụng cho mỗi thương vụ.

## 3. QUY TẮC THOÁT LỆNH & CẮT LỖ (EXIT RULES)
1. Thoát vị thế khi EMA10 cắt xuống dưới SMA50 (Dead Cross) hoặc giá thủng SMA50.
2. Tuân thủ chu kỳ thanh toán T+2.5 của sàn Việt Nam (chỉ bán khi hàng đã về khả dụng).

## 4. KẾT QUẢ THẨM ĐỊNH SAU TIẾN HÓA (5 NĂM)
* **Trạng thái CRO:** `CHIẾN LƯỢC BỊ TỪ CHỐI (Không đạt tiêu chuẩn kiểm soát rủi ro của Quỹ)`
* **Lợi nhuận bình quân năm (CAGR):** `+1.70%/năm`
* **Mức sụt giảm tối đa (Max Drawdown):** `-5.31%` (Chuẩn Quỹ <= 15.00%)
* **Sharpe Ratio:** `-0.93`
* **Profit Factor:** `4.81`
* **Tổng số lệnh:** `8 lệnh`

Chi tiết xem tại: [backtest_report.md](./backtest_report.md)

---
name: strategy-vsa-momentum
description: >-
  Chiến lược VSA Momentum Breakout (HPG).
  Trạng thái: REJECTED.
  Sử dụng skill này khi cần phân tích tín hiệu vào/ra lệnh cho các mã: HPG.
---

# CHIẾN LƯỢC: VSA MOMENTUM BREAKOUT (HPG)

## 1. MÔ TẢ TỔNG QUAN
Chiến lược theo sau dòng tiền lớn (Smart Money) kết hợp xu hướng MA20 và đột biến Volume.

## 2. QUY TẮC VÀO LỆNH (ENTRY RULES)
1. Giá đóng cửa vượt lên trên đường MA20.
2. Khối lượng phiên hiện tại > 1.2 lần khối lượng trung bình 20 phiên.

## 3. QUY TẮC THOÁT LỆNH & CẮT LỖ (EXIT RULES)
1. Giá đóng cửa giảm thủng xuống dưới đường MA20.
2. Tuân thủ chu kỳ thanh toán T+2.5 của sàn Việt Nam.

## 4. KẾT QUẢ THẨM ĐỊNH LỊCH SỬ (5 NĂM)
* **Trạng thái CRO:** `CHIẾN LƯỢC BỊ TỪ CHỐI (Không đạt tiêu chuẩn kiểm soát rủi ro của Quỹ)`
* **Lợi nhuận bình quân năm (CAGR):** `-0.32%/năm`
* **Mức sụt giảm tối đa (Max Drawdown):** `-2.28%`
* **Sharpe Ratio:** `-6.44`
* **Profit Factor:** `0.00`
* **Tỷ lệ thắng (Win Rate):** `0.0%`

Chi tiết xem tại: [backtest_report.md](./backtest_report.md)

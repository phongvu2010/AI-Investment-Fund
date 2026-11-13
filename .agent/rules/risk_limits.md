# BỘ QUY TẮC QUẢN TRỊ RỦI RO & HẠN MỨC DANH MỤC (RISK LIMITS)

---

## 1. CÁC QUY TẮC THÉP BẤT KHẢ XÂM PHẠM (HARD RULES) - KIẾN TRÚC CORE-SATELLITE (DUAL-BOOK)

Hệ thống phân tách thành 2 Sổ cái độc lập với khẩu vị rủi ro và triết lý đầu tư riêng biệt:

### 1.1 Sổ Chiến Lược CORE (Fundamental Trung & Dài Hạn):
* **Hạn mức tổng sổ (`CORE_MAX_ALLOCATION_PCT`):** Tối đa **70% tổng NAV** của Quỹ.
* **Hạn mức vị thế đơn lẻ (`CORE_MAX_POSITION_PCT`):** Tối đa **25% tổng NAV** cho một mã cổ phiếu cơ bản.
* **Ngưỡng Cắt lỗ cứng (`CORE_HARD_STOP_LOSS_PCT`):** Khóa cứng ở mức **-15.0%** so với giá vốn bình quân (cho phép chịu đựng biến động chu kỳ và kiểm định nền).

### 1.2 Sổ Chiến Lược QUANT (Trading Ngắn Hạn & Xung Lượng):
* **Hạn mức tổng sổ (`QUANT_MAX_ALLOCATION_PCT`):** Tối đa **30% tổng NAV** của Quỹ.
* **Hạn mức vị thế đơn lẻ (`QUANT_MAX_POSITION_PCT`):** Tối đa **15% tổng NAV** cho một mã trading.
* **Ngưỡng Cắt lỗ cứng (`QUANT_HARD_STOP_LOSS_PCT`):** Khóa cứng ở mức **-7.0%** so với giá vốn bình quân (bảo toàn vốn, chống kẹp hàng).

---

## 2. QUY TẮC RỦI RO TOÀN HỆ THỐNG

1. **[HARD RULE 1] Ngắt Mạch Tự Động Khi Thua Lỗ Tuần (Circuit Breaker):**
   * Nếu NAV của Quỹ sụt giảm quá **5.0% trong vòng một tuần**, toàn bộ hoạt động mua mới lập tức bị **ĐÓNG BĂNG**.
   * Quỹ chỉ được phép quản lý và cơ cấu danh mục hiện tại, không được mở thêm vị thế mới cho đến khi hoàn thành buổi họp rà soát chiến lược.

2. **[HARD RULE 2] Bộ Lọc Trạng Thái Thị Trường (Market Regime):**
   * Không giải ngân mua mới khi Macro Agent xác định thị trường đang trong trạng thái **Heavy Downtrend** (VN-Index nằm dưới MA50 và MA200 đang dốc xuống).

---

## 2. CÁC NGUYÊN TẮC CHIẾN LƯỢC ĐỀ XUẤT (SOFT RULES)

1. **Tỷ Lệ Lợi Nhuận / Rủi Ro ($R:R$):**
   * Chỉ xem xét giải ngân khi tỷ lệ kỳ vọng $R:R \ge 2.5:1$ (Ví dụ: Chấp nhận rủi ro cắt lỗ -6% thì mục tiêu lợi nhuận tối thiểu phải là +15%).
2. **Giải Ngân Từng Phần (Kim Tự Tháp Thuận):**
   * Mua thăm dò 30% tại vùng nền tích lũy.
   * Gia tăng 40% khi giá bứt phá (Breakout) kèm dòng tiền nổ volume xác nhận.
   * Giải ngân 30% còn lại khi cổ phiếu kiểm định lại (Pullback) thành công.
3. **Thanh Khoản Tối Thiểu:**
   * Chỉ giao dịch các cổ phiếu có giá trị giao dịch trung bình 20 phiên $\ge 10\text{ tỷ VND/phiên}$ để đảm bảo có thể thoát hàng ngay khi cần thiết.

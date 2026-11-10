# BỘ QUY TẮC QUẢN TRỊ RỦI RO & HẠN MỨC DANH MỤC (RISK LIMITS)

---

## 1. CÁC QUY TẮC THÉP BẤT KHẢ XÂM PHẠM (HARD RULES)

1. **[HARD RULE 1] Hạn Mức Phân Bổ Vốn Đơn Lẻ (Position Sizing):**
   * Không bao giờ giải ngân quá **20.0% tổng NAV** của Quỹ vào một mã cổ phiếu duy nhất tại bất kỳ thời điểm nào.
   * Danh mục phải duy trì tối thiểu từ 3 đến 6 mã cổ phiếu thuộc các nhóm ngành khác nhau để phân tán rủi ro.

2. **[HARD RULE 2] Kỷ Luật Cắt Lỗ Cứng (Hard Stop-Loss):**
   * Mọi vị thế mở mới **bắt buộc** phải có ngưỡng Stop-Loss xác định trước.
   * Ngưỡng cắt lỗ tối đa cho phép là **-7.0%** so với giá vốn bình quân.
   * **CẤM TUYỆT ĐỐI:** Không bao giờ được phép nới lỏng hoặc dời ngưỡng Stop-loss ra xa hơn khi cổ phiếu đang giảm giá. Khi chạm ngưỡng, bắt buộc kích hoạt cảnh báo bán ngay lập tức.

3. **[HARD RULE 3] Ngắt Mạch Tự Động Khi Thua Lỗ Tuần (Circuit Breaker):**
   * Nếu NAV của Quỹ sụt giảm quá **5.0% trong vòng một tuần**, toàn bộ hoạt động mua mới lập tức bị **ĐÓNG BĂNG**.
   * Quỹ chỉ được phép quản lý và cơ cấu danh mục hiện tại, không được mở thêm vị thế mới cho đến khi hoàn thành buổi họp rà soát chiến lược.

4. **[HARD RULE 4] Bộ Lọc Trạng Thái Thị Trường (Market Regime):**
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

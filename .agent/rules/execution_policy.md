# QUY ĐỊNH THỰC THI GIAO DỊCH & ĐỐI SOÁT KẾ TOÁN (EXECUTION POLICY)

---

## 1. NGUYÊN TẮC BẢO MẬT & THỰC THI
1. **Không Tự Động Kết Nối Mật Khẩu/OTP:** Nhằm tuân thủ quy định pháp luật và bảo vệ an toàn tài sản cá nhân, AI không lưu trữ mật khẩu đăng nhập CTCK hay mã SmartOTP.
2. **Kênh Nhận Lệnh Duy Nhất:** Mọi tín hiệu giao dịch được chuyển tới Bạn qua Telegram Bot hoặc Web Dashboard.
3. **Hiệu Lực Lệnh (Valid for Day):**
   * Lệnh đề xuất có hiệu lực trong **suốt phiên giao dịch của ngày hôm đó**.
   * Hệ thống không tự ý hủy lệnh trong phiên để Bạn thoải mái đặt lệnh chờ (LO) trên bảng điện.

---

## 2. QUY CHẾ NHẬP BÙ & ĐỐI SOÁT HỒI TỐ (RECONCILIATION)
1. **Khớp Chuẩn:** Bấm nút `[✅ ĐÃ KHỚP CHUẨN]` trên Telegram khi khớp đúng giá/khối lượng đề xuất.
2. **Khớp Khác Khối Lượng / Giá:** Bác gửi tin nhắn nhanh theo cú pháp `/fill MÃ KHỐI_LƯỢNG GIÁ` hoặc gõ tự nhiên `khớp HPG 5000 giá 28.2`. Hệ thống tự bóc tách và hạch toán đúng giá thực tế.
3. **Nhập Bù Linh Hoạt:** Bác có thể nhập bù vào buổi tối hoặc sáng hôm sau. Cỗ máy kế toán sẽ tự động chạy hồi tố (Recalculate NAV) theo đúng giá đóng cửa ngày hôm đó, đảm bảo sổ sách kế toán khớp 100% với tài khoản chứng khoán thực tế.
4. **Kiểm Toán Trượt Giá (Slippage Audit):** Nếu mức trượt giá thực tế vượt quá $+1.5\%$ so với giá khuyến nghị do mua đuổi giá trần, Auditor Agent sẽ gắn cờ cảnh báo rủi ro thực thi.

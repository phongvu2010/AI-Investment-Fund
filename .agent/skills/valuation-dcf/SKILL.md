---
name: valuation-dcf
description: Kỹ năng định giá doanh nghiệp và chiết khấu dòng tiền (Valuation & DCF) dành cho FA Analyst và Hội đồng Đầu tư AI.
---

# KỸ NĂNG ĐỊNH GIÁ DOANH NGHIỆP & CHIẾT KHẤU DÒNG TIỀN (VALUATION & DCF)

Kỹ năng chuyên sâu dành cho **FA Analyst** và **Hội đồng Đầu tư AI** phục vụ thẩm định Sổ Chiến Lược **CORE (Fundamental Trung & Dài Hạn)**:

---

## 1. NGUYÊN TẮC HOẠT ĐỘNG
* **Nguồn dữ liệu:** `data/fundamental_quarterly.parquet` qua công cụ `tools/fundamental_screener.py` (0 Token, xử lý dữ liệu chuẩn bằng Polars).
* **Ma trận Đánh giá (Fundamental Score 0-100 điểm):**
  1. Tăng trưởng Doanh thu & Lợi nhuận YoY $\ge 15\%$ (25 điểm).
  2. Hiệu quả sử dụng vốn (ROE $\ge 15\%$, Biên lãi gộp $\ge 20\%$) (25 điểm).
  3. Cấu trúc tài chính an toàn ($D/E \le 1.5x$, Dòng tiền hoạt động $OCF / LNST \ge 1.0x$) (30 điểm).
  4. Biên an toàn định giá (P/E $\le 1.2x$ Trung vị 5 năm) (20 điểm).

---

## 2. QUY TRÌNH PHÁT HIỆN RỦI RO KẾ TOÁN (ACCOUNTING RED FLAGS)
Bắt buộc kích hoạt cờ đỏ và quyền phủ quyết (CRO Veto) nếu phát hiện bất kỳ dấu hiệu nào sau đây:
* 🚩 **Lợi nhuận ảo:** Lợi nhuận kế toán dương nhưng Dòng tiền thuần từ HĐKD (OCF) âm.
* 🚩 **Đòn bẩy nguy hiểm:** Tỷ lệ Nợ vay / Vốn chủ sở hữu ($D/E > 2.0x$).
* 🚩 **Định giá bong bóng:** P/E hiện tại cao hơn $1.5x$ mức P/E trung vị 5 năm.
* ⚠️ **Suy thoái biên lợi nhuận:** Biên lợi nhuận gộp sụt giảm liên tiếp hoặc dưới $10\%$.

---

## 3. KHẨU VỊ VỊ THẾ SỔ CORE vs. QUANT
* **Sổ CORE:** Chỉ giải ngân khi `FA Score >= 70` và **KHÔNG CÓ** cờ đỏ trọng yếu (`🚩`).
* **Sổ QUANT:** Ưu tiên xung lượng dòng tiền kỹ thuật & ML Score, nhưng nếu cổ phiếu có `🚩` về OCF hoặc D/E, khối lượng tối đa bị hạ 50%.

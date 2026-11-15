# BÁO CÁO THẨM ĐỊNH CHIẾN LƯỢC ĐẦU TƯ: VSA MOMENTUM BREAKOUT (HPG)
* **Mã cổ phiếu áp dụng:** `HPG`
* **Thời gian kiểm nghiệm:** `4.8 năm` (1746 ngày giao dịch)
* **Vốn khởi điểm giả lập:** `1,000,000,000 VND`
* **Vốn kết thúc (Equity):** `984,649,750 VND`
* **Biểu đồ tương tác HTML:** [apps/api/static/reports/vsa_momentum_breakout_(hpg).html](../../../apps/api/static/reports/vsa_momentum_breakout_(hpg).html)

---

## 1. BẢNG CHỈ SỐ ĐỊNH LƯỢNG (QUANTITATIVE METRICS)

| Chỉ số Hiệu suất | Giá trị Thực tế | Đánh giá Chuẩn mực |
| :--- | :---: | :--- |
| **Tổng Lợi Nhuận (Total Return)** | **-1.54%** | Lợi nhuận gộp toàn chu kỳ |
| **Lợi nhuận Bình quân Năm (CAGR)** | **-0.32%/năm** | Tỷ suất sinh lời kép hàng năm |
| **Mức Sụt Giảm Tối Đa (Max Drawdown)** | **-2.28%** | Rủi ro sụt giảm vốn từ đỉnh |
| **Sharpe Ratio (Rủi ro tổng thể)** | **-6.44** | Đo lường tỷ suất trên biến động |
| **Sortino Ratio (Rủi ro sụt giảm)** | **-8.49** | Chỉ tính biến động chiều giảm |
| **Calmar Ratio** | **-0.14** | Tỷ lệ CAGR / Max Drawdown |
| **Tỷ lệ Thắng (Win Rate)** | **0.0%** | % Lệnh có lợi nhuận dương |
| **Hệ số Lợi nhuận/Lỗ (Profit Factor)**| **0.00** | Tổng tiền thắng / Tổng tiền thua |
| **Tổng Số Lệnh Khớp (Total Trades)**| **2 lệnh** | Độ tin cậy mẫu thống kê |
| **Lãi Trung Bình Mỗi Lệnh** | **-1.74%** | Kỳ vọng sinh lời trung bình/deal |
| **Thời Gian Nắm Giữ Trung Bình** | **4.0 ngày** | Chu kỳ nắm giữ vị thế ($T+2.5$) |

---

## 2. KẾT LUẬN THẨM ĐỊNH CỦA GIÁM ĐỐC RỦI RO (CRO EVALUATION)

### 📋 Bảng Đối chiếu Kỷ luật Quỹ:
* ❌ KHÔNG ĐẠT: Sharpe = -6.44 (Yêu cầu >= 1.20)
* ✅ ĐẠT: Max Drawdown = 2.28% (Yêu cầu <= 15.00%)
* ❌ KHÔNG ĐẠT: Profit Factor = 0.00 (Yêu cầu >= 1.80)
* ❌ KHÔNG ĐẠT: Tổng số lệnh = 2 (Yêu cầu >= 15 lệnh)
* ✅ ĐẠT: ĐẠT CHUẨN: Out-of-Sample Sharpe = 429.06 (Giữ vững 607.7% hiệu suất In-Sample)

### ⚖️ PHÁN QUYẾT CUỐI CÙNG:
> **CHIẾN LƯỢC BỊ TỪ CHỐI (Không đạt tiêu chuẩn kiểm soát rủi ro của Quỹ)**

---

## 3. THẨM ĐỊNH CHỐNG OVERFITTING (OUT-OF-SAMPLE VERIFICATION)

| Chỉ số Đối sánh | Tập Huấn Luyện (In-Sample 70%) | Tập Kiểm Định (Out-of-Sample 30%) | Nhận định |
| :--- | :---: | :---: | :--- |
| **Tỷ số Sharpe** | **70.60** | **429.06** | Giữ vững **607.7%** (Suy giảm: 0.0%) |
| **Max Drawdown** | **-5.56%** | **-2.28%** | Rủi ro sụt giảm thực tế |
| **Tỷ lệ Thắng** | **0.0%** | **0.0%** | Tỷ lệ thắng độc lập |
| **Số Lệnh Khớp** | **2 lệnh** | **2 lệnh** | Mẫu kiểm chứng |

> **Phán Quyết Chống Overfitting:** `[ROBUST]` — ✅ Chiến lược ROBUST (Bền vững): Out-of-Sample Sharpe 429.06 duy trì 607.7% hiệu suất In-Sample.


# WORKFLOW 03: QUY TRÌNH THỰC THI LỆNH & ĐỐI SOÁT (ORDER EXECUTION & RECONCILIATION)

---

## 1. MỤC TIÊU
Đảm bảo luồng giao dịch bán tự động (Semi-Autonomous) diễn ra trơn tru, bảo mật tuyệt đối SmartOTP của Bạn và hạch toán đúng giá khớp thực tế.

---

## 2. QUY TRÌNH THỰC THI CHI TIẾT

```mermaid
sequenceDiagram
    autonumber
    actor Bạn as Bạn (Chủ Quỹ)
    participant Tele as Telegram Bot
    participant App as App CTCK (VPS/SSI/TCBS)
    participant DB as SQLite (fund_vault.db)
    participant Auditor as Auditor Agent

    Tele->>Bạn: Gửi Tờ trình Mua HPG 5.000 CP @ 28.2 (Kèm 3 nút bấm)
    Bạn->>App: Mở app CTCK đặt Lệnh Chờ (LO) tại 28.2
    Note over Bạn,App: Lệnh nằm chờ trên sàn (không giới hạn 15 phút)
    App-->>Bạn: Thông báo "Khớp lệnh thành công 5.000 HPG @ 28.1"
    
    alt Trường hợp 1: Bấm xác nhận ngay
        Bạn->>Tele: Bấm [ ĐÃ KHỚP CHUẨN] hoặc [✍️ BÁO KHỚP KHÁC]
        Tele->>DB: Ghi nhận khớp: trừ tiền mặt, cập nhật danh mục
        DB->>Auditor: Đo lường độ trượt giá (Slippage)
    else Trường hợp 2: Bạn bận đến tối hoặc hôm sau
        Note over DB: Lệnh chuyển sang trạng thái "TẠM TREO CHỜ XÁC NHẬN"
        Bạn->>Tele: Nhắn bù: "/fill HPG 5000 28.1"
        Tele->>DB: Tự động chạy Hồi tố Kế toán (Recalculate NAV)
    end
```

### Các Hành Động Chính:
1. **Bạn Đặt Lệnh Trên App:** Đặt lệnh Giới hạn (LO) tại vùng giá đề xuất.
2. **Khớp Lệnh Thực Tế:** 
   * Nếu khớp đúng $\to$ Bấm nút `[✅ ĐÃ KHỚP CHUẨN]`.
   * Nếu khớp lệch giá/khối lượng $\to$ Nhắn `khớp HPG 5000 giá 28.1` hoặc gõ `/fill`.
3. **Kế Toán Tự Động:** Hệ thống trừ tiền mặt, tính phí CTCK 0.15%, tính giá vốn bình quân mới cho cổ phiếu.

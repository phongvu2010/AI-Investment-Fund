# WORKFLOW 04: CHỐT SỔ KẾ TOÁN NAV & ĐỒNG BỘ DỮ LIỆU ĐÊM (NIGHTLY ACCOUNTING)

---

## 1. MỤC TIÊU
Thực hiện chốt sổ tài sản ròng (NAV Mark-to-Market), khấu trừ chi phí ẩn và đồng bộ nến ngày mới nhất từ BigQuery về file Parquet 5 năm (hoàn toàn 0 Token).

---

## 2. QUY TRÌNH THỰC HIỆN THEO MỐC THỜI GIAN

```
[15:30 PM] Chốt sổ Kế toán NAV Ngày:
  - Lấy giá đóng cửa sàn HSX/HNX.
  - Cập nhật thị giá cho danh mục portfolio.
  - Tính toán Realized/Unrealized PnL và NAV ròng.
  - Ghi vĩnh viễn vào bảng nav_daily trong SQLite.

[20:00 PM] Đối soát Giao dịch với Bạn:
  - Nếu còn lệnh nào ở trạng thái "Chờ xác nhận", Bot Telegram gửi tin nhắn nhẹ:
    "Bác đã khớp được lệnh này chưa để em chốt sổ NAV ạ?"

[20:30 PM] Cloud Run nạp dữ liệu vào BigQuery:
  - Hệ thống Cloud Run tự động cào và đổ nến EOD vào BigQuery (kho tổng).

[21:00 PM] Đồng bộ Incremental về máy:
  - Chạy script: `python tools/bigquery_sync.py --mode daily`
  - Kéo ~1.600 dòng nến mới nhất nối vào file data/market_history_5y.parquet.
  - Hoàn tất công tác chuẩn bị dữ liệu cho phiên ngày mai!
```

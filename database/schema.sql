-- ====================================================================
-- SCHEMA CƠ SỞ DỮ LIỆU QUỸ ĐẦU TƯ AI (SQLite - fund_vault.db)
-- Lưu trữ vĩnh viễn: Danh mục, Sổ lệnh, Lịch sử NAV, Cổ tức & Biên bản họp
-- ====================================================================

PRAGMA foreign_keys = ON;

-- 1. BẢNG CÀI ĐẶT HỆ THỐNG & TRẠNG THÁI (SYSTEM SETTINGS)
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 2. BẢNG DANH MỤC NẮM GIỮ HIỆN TẠI (PORTFOLIO)
CREATE TABLE IF NOT EXISTS portfolio (
    ticker TEXT PRIMARY KEY,                   -- Mã cổ phiếu (ví dụ: HPG, SSI, FPT)
    quantity INTEGER NOT NULL CHECK (quantity >= 0), -- Số lượng cổ phiếu nắm giữ
    avg_buy_price REAL NOT NULL,              -- Giá vốn bình quân (VND)
    current_price REAL DEFAULT 0.0,           -- Giá thị trường cập nhật gần nhất
    market_value REAL DEFAULT 0.0,            -- Giá trị thị trường = quantity * current_price
    unrealized_pnl REAL DEFAULT 0.0,          -- Lãi/lỗ tạm tính = market_value - (quantity * avg_buy_price)
    unrealized_pnl_pct REAL DEFAULT 0.0,      -- % Lãi/lỗ tạm tính
    weight_pct REAL DEFAULT 0.0,              -- Tỷ trọng trên tổng NAV (%)
    first_bought_date TEXT,                   -- Ngày mua đầu tiên (YYYY-MM-DD)
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP -- Thời điểm cập nhật cuối cùng
);

-- 3. BẢNG LỊCH SỬ TẤT CẢ CÁC LỆNH (ORDER HISTORY)
CREATE TABLE IF NOT EXISTS order_history (
    order_id TEXT PRIMARY KEY,                -- Mã định danh lệnh (ví dụ: ORD-20261103-001)
    ticker TEXT NOT NULL,                     -- Mã cổ phiếu
    action TEXT NOT NULL CHECK(action IN ('BUY', 'SELL')), -- Hành động
    order_type TEXT DEFAULT 'LO',             -- Loại lệnh (LO: Limit Order, MP: Market Price)
    proposed_price REAL NOT NULL,             -- Giá AI đề xuất
    proposed_volume INTEGER NOT NULL,         -- Khối lượng AI đề xuất
    executed_price REAL,                      -- Giá khớp thực tế bạn báo về
    executed_volume INTEGER DEFAULT 0,        -- Khối lượng khớp thực tế bạn báo về
    status TEXT NOT NULL CHECK(status IN (
        'PROPOSED',                -- AI mới đề xuất gửi Telegram
        'SUBMITTED',               -- Bạn đã đặt lệnh trên app CTCK, đang chờ sàn khớp
        'FILLED',                  -- Khớp thành công toàn bộ
        'PARTIALLY_FILLED',        -- Mới khớp được một phần
        'CANCELLED',               -- Bạn chủ động hủy
        'EXPIRED',                 -- Hết phiên chưa khớp sàn tự hủy
        'PENDING_RECONCILIATION'   -- Tạm treo chờ bạn đối soát/nhập bù
    )),
    fee REAL DEFAULT 0.0,                     -- Phí giao dịch CTCK (0.15%)
    tax REAL DEFAULT 0.0,                     -- Thuế TNCN khi bán (0.10%)
    slippage_pct REAL DEFAULT 0.0,            -- Độ trượt giá (% chênh giữa giá đề xuất & giá khớp)
    trade_date TEXT NOT NULL,                 -- Ngày giao dịch (YYYY-MM-DD)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,-- Thời điểm AI sinh lệnh
    executed_at TEXT,                         -- Thời điểm bạn xác nhận khớp lệnh
    memo_id TEXT,                             -- Liên kết với Tờ trình đầu tư (nếu có)
    notes TEXT                                -- Ghi chú bổ sung
);

-- 4. BẢNG CHỐT SỔ TÀI SẢN HÀNG NGÀY (NAV DAILY)
CREATE TABLE IF NOT EXISTS nav_daily (
    trade_date TEXT PRIMARY KEY,              -- Ngày chốt sổ (YYYY-MM-DD)
    total_nav REAL NOT NULL,                  -- Tổng tài sản ròng = cash_balance + stock_value
    cash_balance REAL NOT NULL,               -- Số dư tiền mặt khả dụng
    stock_value REAL NOT NULL,                -- Tổng giá trị thị trường của toàn bộ cổ phiếu
    daily_pnl REAL DEFAULT 0.0,               -- Lợi nhuận trong ngày = total_nav(hôm nay) - total_nav(hôm qua)
    daily_pnl_pct REAL DEFAULT 0.0,           -- % Lợi nhuận trong ngày
    cumulative_pnl REAL DEFAULT 0.0,          -- Lợi nhuận lũy kế từ ngày khởi lập Quỹ
    realized_pnl REAL DEFAULT 0.0,            -- Lợi nhuận thực tế đã chốt
    unrealized_pnl REAL DEFAULT 0.0,          -- Lợi nhuận tạm tính các vị thế đang mở
    total_fee REAL DEFAULT 0.0,               -- Tổng phí giao dịch phát sinh trong ngày
    total_tax REAL DEFAULT 0.0,               -- Tổng thuế TNCN phát sinh trong ngày
    margin_interest REAL DEFAULT 0.0,         -- Lãi vay margin phát sinh trong ngày (nếu có)
    nav_per_share REAL DEFAULT 10000.0,       -- Đơn vị chứng chỉ quỹ (chuẩn hóa 10.000 đ)
    notes TEXT,                               -- Nhận định tóm tắt của kế toán
    created_at TEXT DEFAULT CURRENT_TIMESTAMP -- Thời điểm chạy chốt sổ
);

-- 5. BẢNG SỰ KIỆN DOANH NGHIỆP & CỔ TỨC (CORPORATE ACTIONS)
CREATE TABLE IF NOT EXISTS corporate_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,                     -- Mã cổ phiếu
    action_type TEXT NOT NULL CHECK(action_type IN (
        'CASH_DIVIDEND',   -- Cổ tức tiền mặt
        'STOCK_DIVIDEND',  -- Cổ tức cổ phiếu
        'BONUS_SHARES',    -- Cổ phiếu thưởng
        'RIGHT_ISSUE'      -- Quyền mua cổ phiếu phát hành thêm
    )),
    ex_date TEXT NOT NULL,                    -- Ngày giao dịch không hưởng quyền (GDKHQ)
    record_date TEXT,                         -- Ngày chốt danh sách cổ đông
    payment_date TEXT,                        -- Ngày tiền hoặc cổ tức về tài khoản
    ratio REAL DEFAULT 0.0,                   -- Tỷ lệ (ví dụ: 10:1 đối với cổ tức cổ phiếu)
    cash_amount_per_share REAL DEFAULT 0.0,   -- Số tiền mặt/cổ phiếu (trước thuế 5%)
    status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'APPLIED', 'CANCELLED')),
    applied_at TEXT,                          -- Thời điểm hạch toán vào danh mục
    notes TEXT
);

-- 6. BẢNG TỜ TRÌNH & BIÊN BẢN HỌP HỘI ĐỒNG (DECISION MEMOS)
CREATE TABLE IF NOT EXISTS decision_memos (
    memo_id TEXT PRIMARY KEY,                 -- Mã tờ trình (MEMO-20261103-001)
    ticker TEXT NOT NULL,                     -- Mã cổ phiếu
    trade_date TEXT NOT NULL,                 -- Ngày họp
    action TEXT NOT NULL CHECK(action IN ('BUY', 'SELL', 'HOLD')),
    target_price REAL NOT NULL,               -- Giá mục tiêu
    stop_loss_price REAL NOT NULL,            -- Giá cắt lỗ
    target_volume INTEGER NOT NULL,           -- Khối lượng khuyến nghị
    macro_summary TEXT,                       -- Tóm tắt thời tiết thị trường
    bull_points TEXT,                         -- Luận điểm Phe Bò
    bear_points TEXT,                         -- Phản biện Phe Gấu
    cro_evaluation TEXT,                      -- Đánh giá của Giám đốc rủi ro
    human_decision TEXT DEFAULT 'PENDING' CHECK(human_decision IN ('PENDING', 'APPROVED', 'REJECTED', 'MODIFIED')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- CHỈ MỤC TỐI ƯU TỐC ĐỘ TRUY VẤN
CREATE INDEX IF NOT EXISTS idx_order_ticker ON order_history(ticker);
CREATE INDEX IF NOT EXISTS idx_order_date ON order_history(trade_date);
CREATE INDEX IF NOT EXISTS idx_order_status ON order_history(status);
CREATE INDEX IF NOT EXISTS idx_corp_ticker ON corporate_actions(ticker);

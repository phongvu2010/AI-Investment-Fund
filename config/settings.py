"""
Module Cấu hình Hệ thống Quỹ Đầu tư AI Cá nhân.
Quản lý các biến môi trường, đường dẫn tệp tin và các tham số vận hành chuẩn mực.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Xác định thư mục gốc của dự án
BASE_DIR = Path(__file__).resolve().parent.parent

# Tải cấu hình từ file .env (nếu có)
load_dotenv(BASE_DIR / ".env")

# ==========================================
# 1. ĐƯỜNG DẪN CƠ SỞ DỮ LIỆU & DỮ LIỆU THỊ TRƯỜNG
# ==========================================
DATA_DIR = BASE_DIR / "data"
DATABASE_DIR = BASE_DIR / "database"

DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

# Đường dẫn file SQLite lưu trữ giao dịch và kế toán
SQLITE_DB_PATH = DATABASE_DIR / "fund_vault.db"

# Đường dẫn file Parquet 5 năm của 1.600 mã chứng khoán VN
MARKET_PARQUET_PATH = DATA_DIR / "market_history_5y.parquet"

# ==========================================
# 2. CẤU HÌNH GOOGLE CLOUD & BIGQUERY
# ==========================================
# Khớp chính xác với dự án BigQuery thực tế của Bạn
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "your-gcp-project-id")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "vietnam_stocks")
BIGQUERY_TABLE_ADJ = os.getenv("BIGQUERY_TABLE_ADJ", "adj_price")   # Giá điều chỉnh (dùng cho TA & Backtest)
BIGQUERY_TABLE_RAW = os.getenv("BIGQUERY_TABLE_RAW", "raw_price")   # Giá thô (dùng khi cần đối soát)
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

# Thiết lập biến môi trường cho Google SDK nếu có đường dẫn credentials
if GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(GOOGLE_APPLICATION_CREDENTIALS):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS

# ==========================================
# 3. CẤU HÌNH THAM SỐ TÀI CHÍNH & VẬN HÀNH QUỸ
# ==========================================
# Vốn khởi điểm của Quỹ (VND) - Mặc định: 1 tỷ VND
INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", "1000000000"))

# Biểu phí giao dịch thực tế trên sàn VN
BROKER_FEE_RATE = float(os.getenv("BROKER_FEE_RATE", "0.0015"))  # Phí CTCK: 0.15% mỗi chiều
SELL_TAX_RATE = float(os.getenv("SELL_TAX_RATE", "0.0010"))       # Thuế TNCN: 0.10% chiều bán
MARGIN_INTEREST_RATE = float(os.getenv("MARGIN_INTEREST_RATE", "0.12"))  # Lãi margin: 12%/năm

# Quy tắc Kỷ luật Quỹ (Hard Rules)
MAX_POSITION_PCT = float(os.getenv("MAX_POSITION_PCT", "0.20"))    # Tối đa 20% NAV / mã
HARD_STOP_LOSS_PCT = float(os.getenv("HARD_STOP_LOSS_PCT", "0.07")) # Cắt lỗ cứng 7.0%
MAX_WEEKLY_DRAWDOWN_PCT = float(os.getenv("MAX_WEEKLY_DRAWDOWN_PCT", "0.05")) # MDD tuần tối đa 5%

# ==========================================
# 4. CẤU HÌNH TELEGRAM BOT (GIAO DIỆN DI ĐỘNG)
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

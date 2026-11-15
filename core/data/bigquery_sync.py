"""
Module Đồng bộ Dữ liệu từ Google BigQuery về File Parquet 5 Năm.
Tối ưu hóa: Chỉ kéo 1 lần/ngày, lưu nén ZSTD, đọc siêu tốc bằng Polars/DuckDB.
"""

import os
import sys
import argparse
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

# Tự động thêm thư mục gốc dự án vào sys.path để chạy độc lập từ bất kỳ đâu
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import polars as pl
from config import settings

# Thử import Google Cloud BigQuery
try:
    from google.cloud import bigquery
    from google.auth.exceptions import DefaultCredentialsError
    HAS_BIGQUERY_SDK = True
except ImportError:
    HAS_BIGQUERY_SDK = False

class BigQuerySyncEngine:
    """Cỗ máy đồng bộ dữ liệu giữa BigQuery (Cloud) và Parquet (Local)"""

    def __init__(self, table_name: Optional[str] = None):
        self.parquet_path = settings.MARKET_PARQUET_PATH
        self.project_id = settings.GCP_PROJECT_ID
        self.dataset = settings.BIGQUERY_DATASET
        # Mặc định sử dụng bảng Giá điều chỉnh (adj_price) cho Phân tích Kỹ thuật & Backtest
        self.table = table_name or settings.BIGQUERY_TABLE_ADJ
        self.client = None

    def _get_client(self) -> Optional["bigquery.Client"]:
        """Khởi tạo BigQuery Client nếu có thông tin xác thực"""
        if not HAS_BIGQUERY_SDK:
            print("❌ Lỗi: Chưa cài đặt thư viện 'google-cloud-bigquery'.")
            return None

        if self.client is not None:
            return self.client

        try:
            self.client = bigquery.Client(project=self.project_id)
            return self.client
        except Exception as e:
            print(f"⚠️ Không thể kết nối BigQuery bằng Default Credentials: {e}")
            return None

    def sync_full_5y(self, years: int = 5) -> bool:
        """
        Đồng bộ toàn bộ lịch sử 5 năm của 1.600 mã từ BigQuery về file Parquet.
        Chỉ cần chạy 1 lần duy nhất khi khởi tạo dự án.
        """
        client = self._get_client()
        if client is None:
            print("💡 Hãy cấu hình GOOGLE_APPLICATION_CREDENTIALS trong file .env")
            return False

        start_date = (date.today() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
        query = f"""
            SELECT 
                UPPER(symbol) AS ticker,
                CAST(trading_date AS STRING) AS trade_date,
                CAST(open_price AS FLOAT64) AS open,
                CAST(high_price AS FLOAT64) AS high,
                CAST(low_price AS FLOAT64) AS low,
                CAST(close_price AS FLOAT64) AS close,
                CAST(total_volume AS INT64) AS volume,
                COALESCE(exchange, 'HOSE') AS exchange
            FROM `{self.project_id}.{self.dataset}.{self.table}`
            WHERE trading_date >= '{start_date}'
            ORDER BY symbol, trading_date ASC
        """
        print(f"⏳ Đang thực thi truy vấn BigQuery tải {years} năm dữ liệu từ bảng `{self.table}` (từ {start_date})...")

        try:
            # Query và chuyển đổi trực tiếp sang Polars qua PyArrow
            query_job = client.query(query)
            arrow_table = query_job.to_arrow()
            df = pl.from_arrow(arrow_table)

            print(f"✅ Tải thành công {len(df):,} dòng nến từ BigQuery.")
            self._save_parquet(df)
            return True
        except Exception as e:
            print(f"❌ Lỗi truy vấn BigQuery: {e}")
            return False

    def sync_incremental_daily(self, days: int = 3) -> bool:
        """
        Đồng bộ nến mới nhất hàng đêm lúc 21h00 (sau khi Cloud Run tải lúc 20h30).
        Chỉ query 2-3 ngày gần nhất để nối vào file Parquet 5 năm hiện có.
        """
        client = self._get_client()
        if client is None:
            print("💡 Không thể kết nối BigQuery để đồng bộ nến ngày.")
            return False

        if not self.parquet_path.exists():
            print("⚠️ Chưa có file Parquet 5 năm. Chuyển sang chế độ tải Full 5 năm...")
            return self.sync_full_5y()

        start_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
        query = f"""
            SELECT 
                UPPER(symbol) AS ticker,
                CAST(trading_date AS STRING) AS trade_date,
                CAST(open_price AS FLOAT64) AS open,
                CAST(high_price AS FLOAT64) AS high,
                CAST(low_price AS FLOAT64) AS low,
                CAST(close_price AS FLOAT64) AS close,
                CAST(total_volume AS INT64) AS volume,
                COALESCE(exchange, 'HOSE') AS exchange
            FROM `{self.project_id}.{self.dataset}.{self.table}`
            WHERE trading_date >= '{start_date}'
            ORDER BY symbol, trading_date ASC
        """
        print(f"⏳ Đang query nến ngày mới nhất từ BigQuery bảng `{self.table}` ({start_date} -> nay)...")

        try:
            query_job = client.query(query)
            arrow_table = query_job.to_arrow()
            new_df = pl.from_arrow(arrow_table)

            if len(new_df) == 0:
                print("ℹ️ BigQuery chưa có dữ liệu mới hơn.")
                return True

            print(f"📥 Đã tải {len(new_df):,} dòng nến mới.")

            # Đọc file Parquet cũ và ghép nối (Concat + Deduplicate)
            old_df = pl.read_parquet(self.parquet_path)
            merged_df = pl.concat([old_df, new_df]).unique(subset=["ticker", "trade_date"], keep="last")
            merged_df = merged_df.sort(["ticker", "trade_date"])

            self._save_parquet(merged_df)
            print("✅ Đã cập nhật nến ngày mới vào kho dữ liệu Parquet thành công.")
            return True
        except Exception as e:
            print(f"❌ Lỗi đồng bộ nến ngày: {e}")
            return False

    def _save_parquet(self, df: pl.DataFrame):
        """Lưu DataFrame xuống file Parquet nén ZSTD tối ưu tốc độ đọc"""
        self.parquet_path.parent.mkdir(parents=True, exist_ok=True)
        # Ép kiểu dữ liệu chuẩn xác
        cols_to_cast = [
            pl.col("ticker").cast(pl.String),
            pl.col("trade_date").cast(pl.String),
            pl.col("open").cast(pl.Float64),
            pl.col("high").cast(pl.Float64),
            pl.col("low").cast(pl.Float64),
            pl.col("close").cast(pl.Float64),
            pl.col("volume").cast(pl.Int64)
        ]
        if "exchange" in df.columns:
            cols_to_cast.append(pl.col("exchange").cast(pl.String))

        typed_df = df.with_columns(cols_to_cast)

        typed_df.write_parquet(
            self.parquet_path,
            compression="zstd",
            compression_level=3,
            statistics=True
        )
        file_size_mb = self.parquet_path.stat().st_size / (1024 * 1024)
        num_tickers = typed_df["ticker"].n_unique()
        print(f"💾 Đã lưu file: {self.parquet_path}")
        print(f"📊 Thống kê: {len(typed_df):,} dòng | {num_tickers} mã CP | Dung lượng: {file_size_mb:.2f} MB")

    def generate_demo_sample_data(self, num_days: int = 1250) -> bool:
        """
        Tạo dữ liệu mẫu 5 năm cho các mã Bluechips hàng đầu (VN30)
        Giúp kiểm thử toàn bộ hệ thống ngay lập tức khi chưa cắm key BigQuery.
        """
        import numpy as np

        print(f"🛠️ Đang khởi tạo bộ dữ liệu 5 năm mẫu ({num_days} phiên giao dịch)...")
        tickers = ["HPG", "SSI", "FPT", "VCB", "MWG", "TCB", "VHM", "MBB", "STB", "VNM"]

        end_date = date.today()
        # Tạo chuỗi ngày làm việc (không tính T7, CN)
        all_dates = []
        curr = end_date - timedelta(days=int(num_days * 1.5))
        while len(all_dates) < num_days and curr <= end_date:
            if curr.weekday() < 5:  # Thứ 2 đến Thứ 6
                all_dates.append(curr.strftime("%Y-%m-%d"))
            curr += timedelta(days=1)

        records = []
        np.random.seed(42)

        base_prices = {
            "HPG": 28.0, "SSI": 32.0, "FPT": 130.0, "VCB": 90.0, "MWG": 65.0,
            "TCB": 24.0, "VHM": 42.0, "MBB": 23.0, "STB": 31.0, "VNM": 68.0
        }

        for t in tickers:
            price = base_prices[t]
            for d in all_dates:
                # Mô phỏng biến động ngẫu nhiên hình học (Geometric Brownian Motion)
                ret = np.random.normal(0.0005, 0.02)
                close_p = round(max(5.0, price * (1 + ret)), 2)
                high_p = round(close_p * (1 + abs(np.random.normal(0, 0.01))), 2)
                low_p = round(close_p * (1 - abs(np.random.normal(0, 0.01))), 2)
                open_p = round((high_p + low_p) / 2, 2)
                vol = int(np.random.lognormal(14.5, 0.6))

                records.append({
                    "ticker": t,
                    "trade_date": d,
                    "open": open_p,
                    "high": high_p,
                    "low": low_p,
                    "close": close_p,
                    "volume": vol
                })
                price = close_p

        df = pl.DataFrame(records)
        self._save_parquet(df)
        print("🎉 Đã tạo thành công bộ dữ liệu mẫu 5 năm cho các mã Bluechips!")
        return True


def main():
    parser = argparse.ArgumentParser(description="Công cụ Đồng bộ Dữ liệu BigQuery -> Parquet 5 Năm")
    parser.add_argument("--mode", choices=["full", "daily", "demo"], default="daily",
                        help="Chế độ: full (5 năm), daily (nến ngày), demo (tạo dữ liệu mẫu)")
    args = parser.parse_args()

    engine = BigQuerySyncEngine()
    if args.mode == "full":
        engine.sync_full_5y()
    elif args.mode == "daily":
        engine.sync_incremental_daily()
    elif args.mode == "demo":
        engine.generate_demo_sample_data()

if __name__ == "__main__":
    main()

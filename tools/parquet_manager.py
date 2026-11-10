"""
Module Quản trị & Truy vấn Kho Dữ liệu Parquet 5 Năm.
Sử dụng DuckDB và Polars để truy vấn dữ liệu 1.600 mã trong vài miligiây (0 Token).
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Tự động thêm thư mục gốc dự án vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import duckdb
import polars as pl
from config import settings

class ParquetMarketDataManager:
    """Trình truy vấn dữ liệu thị trường Parquet siêu tốc bằng DuckDB"""

    def __init__(self, parquet_path: Optional[Path] = None):
        self.parquet_path = parquet_path or settings.MARKET_PARQUET_PATH

    def is_ready(self) -> bool:
        """Kiểm tra xem file Parquet đã tồn tại và có dữ liệu chưa"""
        return self.parquet_path.exists() and self.parquet_path.stat().st_size > 0

    def get_summary(self) -> Dict[str, Any]:
        """Lấy thông tin tổng quan về kho dữ liệu Parquet"""
        if not self.is_ready():
            return {"status": "EMPTY", "message": "Chưa có file Parquet dữ liệu 5 năm."}

        # Sử dụng DuckDB truy vấn trực tiếp file Parquet không cần load toàn bộ vào RAM
        query = f"""
            SELECT 
                COUNT(*) AS total_rows,
                COUNT(DISTINCT ticker) AS total_tickers,
                MIN(trade_date) AS min_date,
                MAX(trade_date) AS max_date
            FROM '{self.parquet_path}';
        """
        rows = duckdb.query(query).fetchall()
        res = rows[0] if rows else (0, 0, "", "")
        file_size_mb = self.parquet_path.stat().st_size / (1024 * 1024)

        return {
            "status": "READY",
            "file_path": str(self.parquet_path),
            "file_size_mb": round(file_size_mb, 2),
            "total_rows": res[0],
            "total_tickers": res[1],
            "from_date": res[2],
            "to_date": res[3]
        }

    def get_ticker_history(self, ticker: str, days: int = 250) -> pl.DataFrame:
        """
        Lấy chuỗi nến lịch sử của một mã cổ phiếu (mặc định 250 phiên ~ 1 năm).
        Sử dụng cơ chế Pushdown Filter của Parquet để đọc siêu tốc (0.005s).
        """
        if not self.is_ready():
            return pl.DataFrame()

        query = f"""
            SELECT ticker, trade_date, open, high, low, close, volume
            FROM '{self.parquet_path}'
            WHERE ticker = '{ticker.upper()}'
            ORDER BY trade_date DESC
            LIMIT {days};
        """
        df = duckdb.query(query).pl()
        return df.sort("trade_date")

    def get_latest_close_prices(self) -> Dict[str, float]:
        """Lấy giá đóng cửa mới nhất của tất cả các mã trên sàn"""
        if not self.is_ready():
            return {}

        query = f"""
            WITH ranked_prices AS (
                SELECT ticker, close, trade_date,
                       ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trade_date DESC) as rn
                FROM '{self.parquet_path}'
            )
            SELECT ticker, close FROM ranked_prices WHERE rn = 1;
        """
        rows = duckdb.query(query).fetchall()
        return {row[0]: float(row[1]) for row in rows}

    def scan_breakout_vol_candidates(self, min_vol_ratio: float = 1.5, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Quét nhanh các mã cổ phiếu có khối lượng đột biến phiên gần nhất (Volume > 1.5 lần trung bình 20 phiên).
        Chạy bằng SQL DuckDB trong 0.05 giây!
        """
        if not self.is_ready():
            return []

        query = f"""
            WITH daily_stats AS (
                SELECT 
                    ticker,
                    trade_date,
                    close,
                    volume,
                    AVG(volume) OVER (PARTITION BY ticker ORDER BY trade_date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) as avg_vol_20,
                    AVG(close) OVER (PARTITION BY ticker ORDER BY trade_date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) as ma20
                FROM '{self.parquet_path}'
            ),
            latest_day AS (
                SELECT MAX(trade_date) as max_date FROM '{self.parquet_path}'
            )
            SELECT 
                d.ticker,
                d.trade_date,
                d.close,
                d.ma20,
                d.volume,
                d.avg_vol_20,
                ROUND(d.volume / NULLIF(d.avg_vol_20, 0), 2) AS vol_ratio,
                ROUND(((d.close - d.ma20) / NULLIF(d.ma20, 0)) * 100, 2) AS diff_ma20_pct
            FROM daily_stats d
            JOIN latest_day l ON d.trade_date = l.max_date
            WHERE d.volume > {min_vol_ratio} * d.avg_vol_20
              AND d.close > d.ma20
              AND d.avg_vol_20 > 50000 -- Loại bỏ cổ phiếu rác thanh khoản quá thấp
            ORDER BY vol_ratio DESC
            LIMIT {limit};
        """
        res = duckdb.query(query).fetchall()
        columns = ["ticker", "trade_date", "close", "ma20", "volume", "avg_vol_20", "vol_ratio", "diff_ma20_pct"]
        return [dict(zip(columns, row)) for row in res]

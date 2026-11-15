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
import numpy as np
from config import settings
from core.data.intraday_data_feed import IntradayDataFeed

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

    def get_ticker_history(self, ticker: str, days: int = 250, include_intraday: bool = True) -> pl.DataFrame:
        """
        Lấy chuỗi nến lịch sử của một mã cổ phiếu (mặc định 250 phiên ~ 1 năm).
        Sử dụng cơ chế Pushdown Filter của Parquet để đọc siêu tốc (0.005s).
        Hỗ trợ tích hợp nến thời gian thực Intraday (vnstock / Real-time feed) nếu include_intraday = True.
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
        df = duckdb.query(query).pl().sort("trade_date")

        # Tích hợp nến thời gian thực Intraday của phiên hiện tại nếu có
        if include_intraday and len(df) > 0:
            try:
                median_close = float(df["close"].median() or 0.0)
                price_scale = 1000.0 if (0 < median_close < 1000.0) else 1.0
                feed = IntradayDataFeed()
                live_bar = feed.get_live_bar(ticker, price_scale=price_scale)

                if live_bar:
                    live_date = str(live_bar["trade_date"])
                    last_hist_date = str(df["trade_date"][-1])

                    # Nếu nến live cùng ngày với nến cuối trong parquet: cập nhật nến live
                    if live_date == last_hist_date:
                        df = df.filter(pl.col("trade_date") != live_date)

                    # Ghép nến thời gian thực vào đuôi chuỗi lịch sử
                    live_row = pl.DataFrame([{
                        "ticker": ticker.upper(),
                        "trade_date": live_date,
                        "open": float(live_bar["open"]),
                        "high": float(live_bar["high"]),
                        "low": float(live_bar["low"]),
                        "close": float(live_bar["close"]),
                        "volume": float(live_bar["volume"])
                    }])
                    df = pl.concat([df, live_row]).sort("trade_date")
            except Exception:
                # Nếu không có mạng hoặc nguồn realtime tạm gián đoạn, giữ nguyên nến lịch sử Parquet
                pass

        return df

    def get_latest_close_prices(self, include_intraday: bool = True) -> Dict[str, float]:
        """
        Lấy giá đóng cửa mới nhất của tất cả các mã trên sàn.
        Nếu include_intraday = True: tự động đè giá khớp trực tiếp Intraday từ bảng giá thời gian thực.
        """
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
        prices = {row[0]: float(row[1]) for row in rows}

        if include_intraday:
            try:
                vals = [v for v in prices.values() if v > 0]
                scale = 1000.0 if (vals and float(np.median(vals)) < 1000.0) else 1.0
                feed = IntradayDataFeed()
                live_dict = feed.get_live_prices(price_scale=scale)
                if live_dict:
                    prices.update(live_dict)
            except Exception:
                pass

        return prices

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

    def get_ticker_liquidity_metrics(self, ticker: str, window: int = 20) -> Dict[str, Any]:
        """
        Tính toán các chỉ số thanh khoản thực tế 20 phiên của cổ phiếu:
        - ADV (Average Daily Volume): Khối lượng giao dịch trung bình ngày.
        - ADTV (Average Daily Turnover Value): Giá trị giao dịch trung bình ngày (VND & Tỷ VND).
        - Max Executable Volume: Khối lượng tối đa Quỹ được phép mua (tránh trượt giá quá 2% ADV).
        - Kiểm tra tính thanh khoản (is_liquid).
        """
        if not self.is_ready():
            return {
                "ticker": ticker.upper(),
                "adv": 0.0,
                "adtv_vnd": 0.0,
                "adtv_billion": 0.0,
                "is_liquid": False,
                "max_allowed_vol": 0,
                "reason": "Kho Parquet chưa sẵn sàng"
            }

        t = ticker.upper()
        query = f"""
            SELECT trade_date, close, volume, open, high, low
            FROM '{self.parquet_path}'
            WHERE ticker = '{t}'
            ORDER BY trade_date DESC
            LIMIT {max(window, 60)};
        """
        rows = duckdb.query(query).fetchall()
        if not rows:
            return {
                "ticker": t,
                "adv": 0.0,
                "adtv_vnd": 0.0,
                "adtv_billion": 0.0,
                "is_liquid": False,
                "max_allowed_vol": 0,
                "is_floor_risk_high": False,
                "is_currently_floor_locked": False,
                "liquidity_stress_score": 0,
                "reason": f"Không có dữ liệu giao dịch cho mã {t}"
            }

        w_rows = rows[:window]
        volumes = [r[2] for r in w_rows if r[2] is not None]
        closes = [r[1] for r in w_rows if r[1] is not None]
        
        if not volumes or not closes:
            return {
                "ticker": t,
                "adv": 0.0,
                "adtv_vnd": 0.0,
                "adtv_billion": 0.0,
                "is_liquid": False,
                "max_allowed_vol": 0,
                "is_floor_risk_high": False,
                "is_currently_floor_locked": False,
                "liquidity_stress_score": 0,
                "reason": "Dữ liệu volume hoặc giá rỗng"
            }

        adv = float(sum(volumes) / len(volumes))
        latest_close = float(closes[0])
        norm_price = latest_close * 1000.0 if latest_close < 1000.0 else latest_close
        adtv_vnd = adv * norm_price
        adtv_billion = round(adtv_vnd / 1_000_000_000.0, 2)

        min_adtv = getattr(settings, "MIN_ADTV_VND", 10_000_000_000.0)
        min_adv = getattr(settings, "MIN_ADV_SHARES", 100_000)
        max_part_rate = getattr(settings, "MAX_PARTICIPATION_RATE", 0.02)

        is_liquid = (adv >= min_adv) and (adtv_vnd >= min_adtv)
        max_allowed_vol = int((adv * max_part_rate) // 100) * 100

        # Phân tích Rủi ro Kẹt Sàn / Trắng Bên Mua (Liquidity Shock & Floor-Lock Fragility)
        # 1. Quét lịch sử 60 phiên gần nhất tìm tần suất rơi sàn (Daily drop <= -6.5%)
        floor_days_count = 0
        max_consecutive_floor = 0
        curr_consecutive_floor = 0

        for i in range(len(rows) - 1):
            c_today = rows[i][1]
            c_prev = rows[i+1][1]
            if c_today and c_prev and c_prev > 0:
                ret = (c_today - c_prev) / c_prev
                if ret <= -0.065:
                    floor_days_count += 1
                    curr_consecutive_floor += 1
                    if curr_consecutive_floor > max_consecutive_floor:
                        max_consecutive_floor = curr_consecutive_floor
                else:
                    curr_consecutive_floor = 0

        # 2. Kiểm tra trạng thái sổ lệnh Live từ IntradayDataFeed
        feed = IntradayDataFeed()
        floor_live = feed.check_floor_lock_risk(t, price_scale=1000.0 if latest_close < 1000.0 else 1.0)
        is_currently_locked = floor_live.get("is_floor_locked", False)
        is_near_floor = floor_live.get("is_near_floor", False)

        # 3. Tính điểm Căng thẳng Thanh khoản (Liquidity Stress Score: 0 - 100)
        stress_score = 0
        if is_currently_locked:
            stress_score += 100
        else:
            if is_near_floor:
                stress_score += 35
            if max_consecutive_floor >= 2:
                stress_score += 40
            elif max_consecutive_floor == 1:
                stress_score += 20
            if floor_days_count >= 3:
                stress_score += 25

        stress_score = min(100, stress_score)
        is_floor_risk_high = (stress_score >= 60) or is_currently_locked

        return {
            "ticker": t,
            "window_days": len(w_rows),
            "adv": round(adv, 0),
            "latest_close": latest_close,
            "norm_price": norm_price,
            "adtv_vnd": adtv_vnd,
            "adtv_billion": adtv_billion,
            "is_liquid": is_liquid,
            "min_adtv_required_billion": round(min_adtv / 1e9, 1),
            "max_allowed_vol": max(100, max_allowed_vol) if is_liquid else 0,
            "participation_rate": max_part_rate,
            "floor_days_count_60d": floor_days_count,
            "max_consecutive_floor_days": max_consecutive_floor,
            "is_currently_floor_locked": is_currently_locked,
            "is_near_floor": is_near_floor,
            "liquidity_stress_score": stress_score,
            "is_floor_risk_high": is_floor_risk_high,
            "floor_warning": floor_live.get("warning_message", "")
        }

    def get_market_regime(self) -> Dict[str, Any]:
        """
        Tính toán Độ rộng Thị trường (Market Breadth) và Trạng thái Chu kỳ (Market Regime)
        hoàn toàn bằng SQL DuckDB trong < 0.05 giây (0 Token):
        - % số mã nằm trên MA20 và MA50.
        - Phân loại: UPTREND / SIDEWAY / DOWNTREND.
        - Đưa ra tỷ lệ phân bổ tài sản khuyến nghị động (Dynamic Asset Allocation):
          + UPTREND: Core 60%, Quant 30%, Cash 10%
          + SIDEWAY: Core 50%, Quant 20%, Cash 30%
          + DOWNTREND (Risk-Off): Max Cash >= 70%, Core 30%, Quant 0% (Đóng băng trading).
        """
        if not self.is_ready():
            return {
                "regime": "SIDEWAY",
                "breadth_ma20_pct": 50.0,
                "breadth_ma50_pct": 50.0,
                "recommended_core_pct": 0.50,
                "recommended_quant_pct": 0.20,
                "recommended_cash_pct": 0.30,
                "description": "Kho Parquet chưa sẵn sàng, sử dụng chế độ mặc định Sideway.",
                "freeze_quant": False
            }

        query = f"""
            WITH ranked_candles AS (
                SELECT 
                    ticker,
                    trade_date,
                    close,
                    AVG(close) OVER (PARTITION BY ticker ORDER BY trade_date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) as ma20,
                    AVG(close) OVER (PARTITION BY ticker ORDER BY trade_date ROWS BETWEEN 50 PRECEDING AND 1 PRECEDING) as ma50,
                    ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trade_date DESC) as rn
                FROM '{self.parquet_path}'
            ),
            latest_status AS (
                SELECT 
                    ticker,
                    close,
                    ma20,
                    ma50,
                    CASE WHEN close > ma20 THEN 1 ELSE 0 END as above_ma20,
                    CASE WHEN close > ma50 THEN 1 ELSE 0 END as above_ma50
                FROM ranked_candles
                WHERE rn = 1
            )
            SELECT 
                COUNT(*) as total_stocks,
                SUM(above_ma20) as count_above_ma20,
                SUM(above_ma50) as count_above_ma50,
                ROUND(AVG(above_ma20) * 100, 1) as pct_above_ma20,
                ROUND(AVG(above_ma50) * 100, 1) as pct_above_ma50
            FROM latest_status;
        """
        res = duckdb.query(query).fetchall()
        row = res[0] if res else None
        if not row or row[0] == 0:
            return {
                "regime": "SIDEWAY",
                "breadth_ma20_pct": 50.0,
                "breadth_ma50_pct": 50.0,
                "recommended_core_pct": 0.50,
                "recommended_quant_pct": 0.20,
                "recommended_cash_pct": 0.30,
                "description": "Không có dữ liệu nến để tính toán độ rộng.",
                "freeze_quant": False
            }

        total_stocks, cnt_ma20, cnt_ma50, pct_ma20, pct_ma50 = row

        if pct_ma20 >= 60.0:
            regime = "UPTREND"
            rec_core = 0.60
            rec_quant = 0.30
            rec_cash = 0.10
            freeze_quant = False
            desc = f"Thị trường TĂNG TRƯỞNG (Uptrend): Độ rộng thị trường tích cực ({pct_ma20}% mã trên MA20, {pct_ma50}% trên MA50). Dòng tiền lan tỏa mạnh mẽ."
        elif pct_ma20 < 40.0:
            regime = "DOWNTREND"
            rec_core = 0.30
            rec_quant = 0.00
            rec_cash = 0.70
            freeze_quant = True
            desc = f"Thị trường SUY THOÁI / RỦI RO CAO (Downtrend / Risk-Off): Độ rộng suy kiệt ({pct_ma20}% mã trên MA20, {pct_ma50}% trên MA50). Áp lực bán chiếm ưu thế tuyệt đối. Kích hoạt chế độ Max Cash Defense."
        else:
            regime = "SIDEWAY"
            rec_core = 0.50
            rec_quant = 0.20
            rec_cash = 0.30
            freeze_quant = False
            desc = f"Thị trường TÍCH LŨY / PHÂN HÓA (Sideway): Độ rộng cân bằng ({pct_ma20}% mã trên MA20, {pct_ma50}% trên MA50). Dòng tiền luân chuyển cục bộ."

        return {
            "regime": regime,
            "total_stocks": total_stocks,
            "breadth_ma20_pct": pct_ma20,
            "breadth_ma50_pct": pct_ma50,
            "recommended_core_pct": rec_core,
            "recommended_quant_pct": rec_quant,
            "recommended_cash_pct": rec_cash,
            "freeze_quant": freeze_quant,
            "description": desc
        }

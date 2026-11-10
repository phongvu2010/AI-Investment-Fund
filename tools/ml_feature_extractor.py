"""
Bộ Trích Xuất Ma Trận Đặc Trưng Định Lượng & Gán Nhãn Đa Chiều (ML Feature Extractor).
Chuẩn hóa dữ liệu tài chính cho mô hình Machine Learning / Deep Learning:
1. Tính toán 15 đặc trưng kỹ thuật & dòng tiền chuẩn hóa (Stationary Features).
2. Áp dụng kỹ thuật gán nhãn 3 Rào cản (Triple-Barrier Method của Marcos López de Prado).
3. Độc lập 100% với các chiến lược giao dịch con.
"""

import sys
import argparse
from pathlib import Path
from typing import Optional, List, Tuple
import numpy as np
import polars as pl

# Thêm thư mục gốc dự án vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings

class MLFeatureExtractor:
    """Bộ trích xuất đặc trưng định lượng & gán nhãn Triple-Barrier toàn thị trường"""

    def __init__(
        self,
        parquet_path: Optional[Path] = None,
        take_profit_pct: float = 0.05,  # Rào cản trên: +5.0%
        stop_loss_pct: float = 0.03,    # Rào cản dưới: -3.0%
        barrier_bars: int = 5           # Khung thời gian nắm giữ tối đa: 5 phiên (T+2.5)
    ):
        self.parquet_path = parquet_path or settings.MARKET_PARQUET_PATH
        self.tp_pct = take_profit_pct
        self.sl_pct = stop_loss_pct
        self.barrier_bars = barrier_bars

        # Danh sách 15 đặc trưng chuẩn hóa (Stationary Features)
        self.feature_columns = [
            "ret_1d", "ret_3d", "ret_5d", "ret_10d", "ret_20d",
            "rel_ret_5d", "rel_ret_20d",
            "vol_ratio_20", "vol_zscore_60",
            "norm_atr_14", "bb_width_20",
            "body_to_range", "upper_wick_ratio", "lower_wick_ratio",
            "rsi_14", "macd_hist_norm"
        ]

    def _extract_ticker_features(self, df_ticker: pl.DataFrame) -> pl.DataFrame:
        """Tính toán 15 đặc trưng kỹ thuật cho một mã cổ phiếu"""
        df = df_ticker.sort("trade_date").clone()

        close = df["close"]
        open_p = df["open"]
        high = df["high"]
        low = df["low"]
        vol = df["volume"]

        # 1. Nhóm Lợi suất Lùi (Momentum Returns)
        ret_1d = close.pct_change(1)
        ret_3d = close.pct_change(3)
        ret_5d = close.pct_change(5)
        ret_10d = close.pct_change(10)
        ret_20d = close.pct_change(20)

        # 2. Nhóm Dòng tiền & Khối lượng (Volume & Liquidity)
        vol_sma20 = vol.rolling_mean(window_size=20)
        vol_ratio_20 = vol / pl.when(vol_sma20 == 0).then(1.0).otherwise(vol_sma20)

        vol_sma60 = vol.rolling_mean(window_size=60)
        vol_std60 = vol.rolling_std(window_size=60)
        vol_zscore_60 = (vol - vol_sma60) / pl.when(vol_std60 == 0).then(1.0).otherwise(vol_std60)

        # 3. Nhóm Biến động & Nến (Volatility & Candlesticks)
        close_prev = close.shift(1)
        tr1 = high - low
        tr2 = (high - close_prev).abs()
        tr3 = (low - close_prev).abs()
        tr = pl.max_horizontal(tr1, tr2, tr3)
        atr_14 = tr.rolling_mean(window_size=14)
        norm_atr_14 = atr_14 / pl.when(close == 0).then(1.0).otherwise(close)

        # Bollinger Bandwidth 20
        bb_mid = close.rolling_mean(window_size=20)
        bb_std = close.rolling_std(window_size=20)
        bb_width_20 = (4.0 * bb_std) / pl.when(bb_mid == 0).then(1.0).otherwise(bb_mid)

        # Cấu trúc nến (Candlestick Ratios)
        full_range = high - low + 1e-8
        body_to_range = (close - open_p).abs() / full_range
        upper_wick = high - pl.max_horizontal(open_p, close)
        lower_wick = pl.min_horizontal(open_p, close) - low
        upper_wick_ratio = upper_wick / full_range
        lower_wick_ratio = lower_wick / full_range

        # 4. Chỉ báo Xung lượng (RSI 14 & MACD Histogram)
        delta = close.diff().to_numpy()
        gain = pl.Series(np.where(delta > 0, delta, 0.0))
        loss = pl.Series(np.where(delta < 0, -delta, 0.0))
        avg_gain = gain.ewm_mean(span=14, adjust=False)
        avg_loss = loss.ewm_mean(span=14, adjust=False)
        rs = avg_gain / np.where(avg_loss == 0, 1e-10, avg_loss)
        rsi_14 = 100.0 - (100.0 / (1.0 + rs))

        ema12 = close.ewm_mean(span=12, adjust=False)
        ema26 = close.ewm_mean(span=26, adjust=False)
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm_mean(span=9, adjust=False)
        macd_hist_norm = (macd_line - signal_line) / pl.when(close == 0).then(1.0).otherwise(close)

        # Ghép đặc trưng vào DataFrame
        feat_df = df.with_columns([
            ret_1d.alias("ret_1d"),
            ret_3d.alias("ret_3d"),
            ret_5d.alias("ret_5d"),
            ret_10d.alias("ret_10d"),
            ret_20d.alias("ret_20d"),
            vol_ratio_20.alias("vol_ratio_20"),
            vol_zscore_60.alias("vol_zscore_60"),
            norm_atr_14.alias("norm_atr_14"),
            bb_width_20.alias("bb_width_20"),
            body_to_range.alias("body_to_range"),
            upper_wick_ratio.alias("upper_wick_ratio"),
            lower_wick_ratio.alias("lower_wick_ratio"),
            rsi_14.alias("rsi_14"),
            macd_hist_norm.alias("macd_hist_norm")
        ])

        return feat_df

    def _apply_triple_barrier_labeling(self, df_ticker: pl.DataFrame) -> pl.DataFrame:
        """
        Gán nhãn theo phương pháp Triple-Barrier (3 Rào Cản):
        Tại mỗi nến t, nhìn về phía trước H phiên:
        - Rào cản trên (+5.0%): Nếu chạm rào cản trên trước -> Label = 1 (Thắng)
        - Rào cản dưới (-3.0%): Nếu chạm rào cản dưới trước -> Label = 0 (Thua / Cắt lỗ)
        - Rào cản thời gian (5 phiên): Nếu sau 5 phiên không chạm đâu, xét lợi nhuận cuối kỳ (> +2% -> 1, ngược lại 0)
        """
        n = len(df_ticker)
        closes = df_ticker["close"].to_numpy()
        highs = df_ticker["high"].to_numpy()
        lows = df_ticker["low"].to_numpy()

        labels = np.zeros(n, dtype=np.int32)
        forward_returns = np.zeros(n, dtype=np.float64)

        for i in range(n):
            if i + self.barrier_bars >= n:
                # Những phiên cuối cùng chưa đủ 5 phiên thì gán nhãn mặc định hoặc lọc bỏ
                labels[i] = -1
                forward_returns[i] = 0.0
                continue

            entry_price = closes[i]
            upper_barrier = entry_price * (1.0 + self.tp_pct)
            lower_barrier = entry_price * (1.0 - self.sl_pct)

            label = 0
            resolved = False

            # Quét từng phiên trong rào cản thời gian
            for k in range(1, self.barrier_bars + 1):
                idx = i + k
                curr_high = highs[idx]
                curr_low = lows[idx]

                hit_upper = curr_high >= upper_barrier
                hit_lower = curr_low <= lower_barrier

                if hit_upper and not hit_lower:
                    label = 1
                    resolved = True
                    break
                elif hit_lower and not hit_upper:
                    label = 0
                    resolved = True
                    break
                elif hit_upper and hit_lower:
                    # Chạm cả hai trong phiên: xem giá đóng cửa phiên đó
                    label = 1 if closes[idx] >= entry_price else 0
                    resolved = True
                    break

            if not resolved:
                # Hết 5 phiên mà không chạm ngưỡng nào: xét lãi cuối kỳ
                end_price = closes[i + self.barrier_bars]
                ret = (end_price - entry_price) / entry_price
                label = 1 if ret >= 0.02 else 0

            labels[i] = label
            forward_returns[i] = (closes[min(i + self.barrier_bars, n - 1)] - entry_price) / entry_price

        labeled_df = df_ticker.with_columns([
            pl.Series("target", labels),
            pl.Series("forward_ret_5d", forward_returns)
        ])

        return labeled_df

    def process_all_market(self) -> pl.DataFrame:
        """
        Xử lý toàn bộ kho dữ liệu Parquet:
        1. Tính đặc trưng kỹ thuật & nến cho từng mã cổ phiếu
        2. Tính sức mạnh tương đối so với trung bình thị trường (Relative Returns)
        3. Áp dụng gán nhãn 3 rào cản
        4. Loại bỏ các dòng nhiễu hoặc chưa đủ dữ liệu ấm (warmup)
        """
        if not self.parquet_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file dữ liệu: {self.parquet_path}")

        print(f"📂 Đang nạp dữ liệu từ: {self.parquet_path}...")
        raw_df = pl.read_parquet(self.parquet_path)
        tickers = raw_df["ticker"].unique().to_list()
        print(f"🔍 Phát hiện {len(tickers)} mã cổ phiếu: {tickers}")

        ticker_frames = []
        for t in tickers:
            df_t = raw_df.filter(pl.col("ticker") == t)
            if len(df_t) < 80:
                continue
            feat_t = self._extract_ticker_features(df_t)
            labeled_t = self._apply_triple_barrier_labeling(feat_t)
            ticker_frames.append(labeled_t)

        all_df = pl.concat(ticker_frames)

        # 5. Tính Lợi suất Tương đối Toàn Sàn (Relative Return vs Market Mean)
        # Tính lợi suất trung bình toàn sàn theo từng ngày giao dịch
        market_mean_df = all_df.group_by("trade_date").agg([
            pl.col("ret_5d").mean().alias("mkt_ret_5d"),
            pl.col("ret_20d").mean().alias("mkt_ret_20d")
        ])

        all_df = all_df.join(market_mean_df, on="trade_date", how="left")
        all_df = all_df.with_columns([
            (pl.col("ret_5d") - pl.col("mkt_ret_5d")).alias("rel_ret_5d"),
            (pl.col("ret_20d") - pl.col("mkt_ret_20d")).alias("rel_ret_20d")
        ])

        # Loại bỏ các dòng khởi động (warmup 60 phiên đầu) và các dòng cuối cùng chưa có nhãn
        clean_df = all_df.filter(
            (pl.col("target") >= 0) &
            pl.col("vol_zscore_60").is_not_null() &
            pl.col("norm_atr_14").is_not_null() &
            pl.col("macd_hist_norm").is_not_null()
        ).sort(["trade_date", "ticker"])

        # Điền các giá trị rỗng nếu có
        clean_df = clean_df.fill_null(0.0)

        print(f"✅ Hoàn tất trích xuất đặc trưng! Tổng số mẫu (samples): {len(clean_df):,}")
        pos_ratio = (clean_df["target"].sum() / len(clean_df)) * 100.0
        print(f"📊 Tỷ lệ mẫu Dương (Thắng - Label 1): {pos_ratio:.2f}% | Mẫu Âm (Label 0): {100.0 - pos_ratio:.2f}%")

        return clean_df

    def export_dataset(self, output_parquet: Path, export_csv: bool = False) -> Path:
        """Xuất bộ dữ liệu sạch ra tệp Parquet và tùy chọn CSV"""
        df = self.process_all_market()
        output_parquet.parent.mkdir(parents=True, exist_ok=True)

        df.write_parquet(output_parquet, compression="zstd")
        print(f"💾 Đã lưu bộ dữ liệu ML huấn luyện: {output_parquet}")

        if export_csv:
            csv_path = output_parquet.with_suffix(".csv")
            df.write_csv(csv_path)
            print(f"📄 Đã xuất thêm tệp CSV (dùng upload lên Kaggle/Colab): {csv_path}")

        return output_parquet


def main():
    parser = argparse.ArgumentParser(description="Bộ Trích Xuất Đặc Trưng ML & Gán Nhãn Triple-Barrier")
    parser.add_argument("--output", default="data/ml_dataset_train.parquet", help="Đường dẫn file parquet đầu ra")
    parser.add_argument("--csv", action="store_true", help="Xuất thêm file CSV để tải lên Kaggle")
    parser.add_argument("--tp", type=float, default=0.05, help="Rào cản chốt lời (mặc định 0.05 = +5%)")
    parser.add_argument("--sl", type=float, default=0.03, help="Rào cản cắt lỗ (mặc định 0.03 = -3%)")
    parser.add_argument("--bars", type=int, default=5, help="Số phiên rào cản thời gian (mặc định 5)")
    args = parser.parse_args()

    extractor = MLFeatureExtractor(
        take_profit_pct=args.tp,
        stop_loss_pct=args.sl,
        barrier_bars=args.bars
    )
    extractor.export_dataset(Path(args.output), export_csv=args.csv)

if __name__ == "__main__":
    main()

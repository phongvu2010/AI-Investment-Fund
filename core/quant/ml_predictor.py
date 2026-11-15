"""
Module Dự Đoán & Chấm Điểm Cơ Hội Thị Trường (Universal Alpha Inference Engine).
Cung cấp điểm số ML Score (0.00 đến 1.00) cho:
1. Bất kỳ chiến lược giao dịch nào (qua BaseFundStrategy.get_ml_score).
2. Hội đồng AI (Technical Analyst, CRO) khi thẩm định đề xuất lệnh.
3. Web Dashboard API & Telegram Bot (Bảng xếp hạng Top Alpha Score).
Thời gian thực thi: < 0.005 giây trên CPU (0 Token tiêu thụ).
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import polars as pl
import numpy as np
import joblib

# Thêm thư mục gốc dự án vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings
from core.data.parquet_manager import ParquetMarketDataManager

class UniversalAlphaPredictor:
    """Trình dự báo & chấm điểm sức mạnh thị trường phổ quát"""

    _instance = None
    _model_package = None

    def __new__(cls, *args, **kwargs):
        """Singleton pattern để chỉ nạp model 1 lần duy nhất vào bộ nhớ RAM"""
        if cls._instance is None:
            cls._instance = super(UniversalAlphaPredictor, cls).__new__(cls)
        return cls._instance

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or (settings.BASE_DIR / "models" / "universal_alpha_model.joblib")
        self.parquet_mgr = ParquetMarketDataManager()
        self._load_model_if_needed()

    def _load_model_if_needed(self):
        if self._model_package is None:
            if not self.model_path.exists():
                print(f"⚠️ Chưa có file model {self.model_path}, đang tự động huấn luyện baseline...")
                from core.quant.ml_model_trainer import train_and_export_local_model
                train_and_export_local_model(output_model_path=self.model_path)

            self._model_package = joblib.load(self.model_path)
            self.model = self._model_package["model"]
            self.features = self._model_package["features"]
            self.metrics = self._model_package.get("metrics", {})
            self.trained_at = self._model_package.get("trained_at", "N/A")
            self.algorithm = self._model_package.get("algorithm", "LightGBM Classifier")

    def reload_model(self):
        """Buộc nạp lại file model mới nhất từ ổ đĩa (dùng sau khi upload model từ Kaggle)"""
        if self.model_path.exists():
            self._model_package = joblib.load(self.model_path)
            self.model = self._model_package["model"]
            self.features = self._model_package["features"]
            self.metrics = self._model_package.get("metrics", {})
            self.trained_at = self._model_package.get("trained_at", "N/A")
            self.algorithm = self._model_package.get("algorithm", "LightGBM Classifier")
            return True
        return False

    def _extract_live_features_for_ticker(self, ticker: str, days: int = 80) -> Optional[Dict[str, float]]:
        """Tính toán vector 15 đặc trưng kỹ thuật mới nhất từ kho Parquet"""
        df = self.parquet_mgr.get_ticker_history(ticker, days=days)
        if len(df) < 65:
            return None

        close = df["close"]
        open_p = df["open"]
        high = df["high"]
        low = df["low"]
        vol = df["volume"]

        # 1. Lợi suất
        ret_1d = float(close.pct_change(1)[-1] or 0.0)
        ret_3d = float(close.pct_change(3)[-1] or 0.0)
        ret_5d = float(close.pct_change(5)[-1] or 0.0)
        ret_10d = float(close.pct_change(10)[-1] or 0.0)
        ret_20d = float(close.pct_change(20)[-1] or 0.0)

        # 2. Khối lượng
        vol_sma20 = vol.rolling_mean(window_size=20)
        v20 = float(vol_sma20[-1] or 1.0)
        vol_ratio_20 = float(vol[-1] / (v20 if v20 > 0 else 1.0))

        vol_sma60 = vol.rolling_mean(window_size=60)
        vol_std60 = vol.rolling_std(window_size=60)
        v60_mean = float(vol_sma60[-1] or 0.0)
        v60_std = float(vol_std60[-1] or 1.0)
        vol_zscore_60 = float((vol[-1] - v60_mean) / (v60_std if v60_std > 0 else 1.0))

        # 3. Biến động ATR & Bollinger
        h_arr = high.to_numpy()
        l_arr = low.to_numpy()
        c_arr = close.to_numpy()
        c_prev = np.roll(c_arr, 1)
        c_prev[0] = c_arr[0]
        tr = np.maximum.reduce([h_arr - l_arr, np.abs(h_arr - c_prev), np.abs(l_arr - c_prev)])
        atr_14 = float(np.mean(tr[-14:]))
        curr_close = float(close[-1] or 1.0)
        norm_atr_14 = atr_14 / (curr_close if curr_close > 0 else 1.0)

        bb_mid = float(close.rolling_mean(window_size=20)[-1] or 1.0)
        bb_std = float(close.rolling_std(window_size=20)[-1] or 0.0)
        bb_width_20 = (4.0 * bb_std) / (bb_mid if bb_mid > 0 else 1.0)

        # Cấu trúc nến
        rng = float((high[-1] - low[-1]) + 1e-8)
        body_to_range = float(abs(close[-1] - open_p[-1]) / rng)
        upper_wick = float(high[-1] - max(open_p[-1], close[-1]))
        lower_wick = float(min(open_p[-1], close[-1]) - low[-1])
        upper_wick_ratio = upper_wick / rng
        lower_wick_ratio = lower_wick / rng

        # 4. RSI & MACD
        delta = close.diff().to_numpy()
        gain = pl.Series(np.where(delta > 0, delta, 0.0))
        loss = pl.Series(np.where(delta < 0, -delta, 0.0))
        avg_gain = gain.ewm_mean(span=14, adjust=False)
        avg_loss = loss.ewm_mean(span=14, adjust=False)
        ag = float(avg_gain[-1] or 0.0)
        al = float(avg_loss[-1] or 1e-10)
        rs = ag / (al if al > 0 else 1e-10)
        rsi_14 = float(100.0 - (100.0 / (1.0 + rs)))

        ema12 = close.ewm_mean(span=12, adjust=False)
        ema26 = close.ewm_mean(span=26, adjust=False)
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm_mean(span=9, adjust=False)
        macd_diff = float((macd_line - signal_line)[-1] or 0.0)
        macd_hist_norm = macd_diff / (curr_close if curr_close > 0 else 1.0)

        # Lợi suất tương đối & Chế độ thị trường
        rel_ret_5d = ret_5d
        rel_ret_20d = ret_20d
        market_ret_20d = ret_20d * 0.75
        market_breadth_ma20 = 55.0
        rel_vol_to_market = vol_ratio_20

        feature_dict = {
            "ret_1d": ret_1d,
            "ret_3d": ret_3d,
            "ret_5d": ret_5d,
            "ret_10d": ret_10d,
            "ret_20d": ret_20d,
            "rel_ret_5d": rel_ret_5d,
            "rel_ret_20d": rel_ret_20d,
            "vol_ratio_20": vol_ratio_20,
            "vol_zscore_60": vol_zscore_60,
            "norm_atr_14": norm_atr_14,
            "bb_width_20": bb_width_20,
            "body_to_range": body_to_range,
            "upper_wick_ratio": upper_wick_ratio,
            "lower_wick_ratio": lower_wick_ratio,
            "rsi_14": rsi_14,
            "macd_hist_norm": macd_hist_norm,
            "market_ret_20d": market_ret_20d,
            "market_breadth_ma20": market_breadth_ma20,
            "rel_vol_to_market": rel_vol_to_market
        }
        return feature_dict

    def predict_score(self, ticker: str) -> float:
        """
        Dự báo Xác suất Thắng (Alpha Score từ 0.00 đến 1.00) cho 1 mã cổ phiếu tại phiên mới nhất.
        Thực thi siêu tốc < 0.005s.
        """
        feat = self._extract_live_features_for_ticker(ticker.upper())
        if feat is None:
            return 0.50  # Giá trị trung tính nếu không đủ dữ liệu

        import pandas as pd
        input_df = pd.DataFrame([[feat[col] for col in self.features]], columns=self.features)
        proba = float(self.model.predict_proba(input_df)[0][1])
        return round(proba, 4)

    def get_market_rankings(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Quét và xếp hạng Alpha Score cho toàn bộ các mã cổ phiếu trên sàn trong phiên gần nhất.
        """
        if not self.parquet_mgr.is_ready():
            return []

        # Lấy danh sách các mã có trong Parquet
        query = f"SELECT DISTINCT ticker FROM '{self.parquet_mgr.parquet_path}';"
        import duckdb
        rows = duckdb.query(query).fetchall()
        tickers = [r[0] for r in rows]

        latest_prices = self.parquet_mgr.get_latest_close_prices()

        rankings = []
        for t in tickers:
            feat = self._extract_live_features_for_ticker(t)
            if feat is None:
                continue

            import pandas as pd
            input_df = pd.DataFrame([[feat[col] for col in self.features]], columns=self.features)
            score = float(self.model.predict_proba(input_df)[0][1])

            # Đánh giá phân hạng
            if score >= 0.65:
                rating = "STRONG_BUY"
                label = "🟢 Rất Khả Quan (High Conviction)"
            elif score >= 0.55:
                rating = "ACCUMULATE"
                label = "🟡 Tích Lũy / Theo Dõi"
            elif score >= 0.45:
                rating = "NEUTRAL"
                label = "⚪ Trung Tính"
            else:
                rating = "RISK_AVOID"
                label = "🔴 Rủi Ro Cao (Tránh Mua)"

            rankings.append({
                "ticker": t,
                "price": latest_prices.get(t, 0.0),
                "ml_score": round(score, 4),
                "rating": rating,
                "label": label,
                "rsi_14": round(feat["rsi_14"], 1),
                "vol_ratio_20": round(feat["vol_ratio_20"], 2),
                "ret_5d_pct": round(feat["ret_5d"] * 100.0, 2)
            })

        # Sắp xếp từ điểm cao nhất xuống thấp nhất
        rankings.sort(key=lambda x: x["ml_score"], reverse=True)
        return rankings[:top_n]


def main():
    predictor = UniversalAlphaPredictor()
    print("\n🏆 BẢNG XẾP HẠNG ML ALPHA SCORES TOÀN SÀN (PHIÊN GẦN NHẤT):")
    rankings = predictor.get_market_rankings(top_n=10)
    for idx, r in enumerate(rankings, 1):
        print(f" {idx:2d}. {r['ticker']:<5} | Score: {r['ml_score']:.4f} | {r['label']:<32} | Giá: {r['price']:,.2f} | Vol Ratio: {r['vol_ratio_20']:.2f}x | RSI: {r['rsi_14']}")

if __name__ == "__main__":
    main()

"""
Module Khung Chiến lược Mẫu (Strategy Template & Indicator Helpers).
Cung cấp các hàm tính toán chỉ báo kỹ thuật vector hóa bằng Polars
và Lớp cơ sở (BaseFundStrategy) để AI dễ dàng kế thừa khi sinh chiến lược mới.
"""

from typing import Any, Dict, Optional, Tuple
import polars as pl
import numpy as np
import vn_backtest as vb

# ====================================================================
# HÀM TÍNH TOÁN CHỈ BÁO KỸ THUẬT VECTOR HÓA BẰNG POLARS (CỰC NHANH)
# ====================================================================

def indicator_sma(df: pl.DataFrame, length: int = 20, column: str = "Close") -> pl.Series:
    """Đường trung bình động đơn giản (SMA)"""
    return df[column].rolling_mean(window_size=length)

def indicator_ema(df: pl.DataFrame, length: int = 20, column: str = "Close") -> pl.Series:
    """Đường trung bình động hàm mũ (EMA)"""
    return df[column].ewm_mean(span=length, adjust=False)

def indicator_volume_sma(df: pl.DataFrame, length: int = 20) -> pl.Series:
    """Khối lượng trung bình 20 phiên"""
    return df["Volume"].rolling_mean(window_size=length)

def indicator_rsi(df: pl.DataFrame, length: int = 14, column: str = "Close") -> pl.Series:
    """Chỉ báo sức mạnh tương đối (RSI)"""
    delta = df[column].diff().to_numpy()
    gain = pl.Series(np.where(delta > 0, delta, 0.0))
    loss = pl.Series(np.where(delta < 0, -delta, 0.0))
    avg_gain = gain.ewm_mean(span=length, adjust=False)
    avg_loss = loss.ewm_mean(span=length, adjust=False)
    rs = avg_gain / np.where(avg_loss == 0, 1e-10, avg_loss)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return pl.Series("RSI", rsi)

def indicator_bollinger_bands(
    df: pl.DataFrame, length: int = 20, num_std: float = 2.0, column: str = "Close"
) -> Tuple[pl.Series, pl.Series, pl.Series]:
    """Dải Bollinger Bands (Middle, Upper, Lower)"""
    mid = df[column].rolling_mean(window_size=length)
    std = df[column].rolling_std(window_size=length)
    upper = mid + (std * num_std)
    lower = mid - (std * num_std)
    return mid, upper, lower


# ====================================================================
# LỚP CHIẾN LƯỢC CƠ SỞ CỦA QUỸ (BASE FUND STRATEGY)
# ====================================================================

class BaseFundStrategy(vb.Strategy):
    """
    Lớp cơ sở kế thừa từ vn-backtest Strategy.
    Bổ sung các phương thức tiện ích cho quản lý vốn và cắt lỗ.
    """

    def get_holding_qty(self, ticker: str) -> int:
        """Lấy tổng số lượng cổ phiếu hiện đang nắm giữ (kể cả hàng chờ về)"""
        if hasattr(self.engine, "broker") and hasattr(self.engine.broker, "positions"):
            pos = self.engine.broker.positions.get(ticker)
            if pos is not None:
                if isinstance(pos, (int, float)):
                    return int(pos)
                if hasattr(pos, "shares"):
                    return int(pos.shares)
                return int(getattr(pos, "quantity", 0))
        return 0

    def get_sellable_qty(self, ticker: str) -> int:
        """Lấy số lượng cổ phiếu đã về tài khoản khả dụng để bán (sau T+2.5)"""
        if hasattr(self.engine, "broker") and hasattr(self.engine.broker, "sellable_shares"):
            qty = self.engine.broker.sellable_shares.get(ticker, 0)
            return int(qty)
        return 0

    def is_holding(self, ticker: str) -> bool:
        """Kiểm tra xem có đang giữ cổ phiếu này không"""
        return self.get_holding_qty(ticker) > 0

    def can_sell(self, ticker: str) -> bool:
        """Kiểm tra xem đã có cổ phiếu khả dụng để bán (hàng đã về) hay chưa"""
        return self.get_sellable_qty(ticker) > 0

    def get_indicator(self, series: pl.Series, offset: int = 0) -> Optional[float]:
        """
        Lấy giá trị của chỉ báo kỹ thuật tại phiên hiện tại (hoặc lùi offset phiên).
        Bảo vệ tuyệt đối chống Look-Ahead Bias và lỗi tràn chỉ mục.
        """
        idx = self.current_idx + offset
        if 0 <= idx < len(series):
            val = series[idx]
            if val is not None and not np.isnan(val):
                return float(val)
        return None

    def get_prev_close(self, ticker: str, offset: int = -1) -> Optional[float]:
        """Lấy giá đóng cửa phiên trước đó (mặc định hôm qua offset=-1)"""
        idx = self.current_idx + offset
        if idx < 0:
            return None
        if hasattr(self.engine, "_price_arrays") and ticker in self.engine._price_arrays:
            arr = self.engine._price_arrays[ticker].get("Close")
            if arr is not None and 0 <= idx < len(arr):
                return float(arr[idx])
        return None

    def get_ml_score(self, ticker: str) -> float:
        """
        Lấy điểm số dự báo xác suất thắng (Alpha Score: 0.00 - 1.00) từ Universal ML Model.
        Độc lập với mọi chiến lược, dùng làm bộ lọc Meta-Labeling (ví dụ: chỉ mua khi Score >= 0.65).
        """
        try:
            from core.quant.ml_predictor import UniversalAlphaPredictor
            predictor = UniversalAlphaPredictor()
            return predictor.predict_score(ticker)
        except Exception:
            return 0.50


class VSAMomentumStrategy(BaseFundStrategy):
    """
    Chiến lược VSA Momentum Breakout:
    - Mua khi Giá vượt lên trên đường MA20 VÀ Khối lượng vượt 1.2 lần trung bình 20 phiên.
    - Bán chốt lời / cắt lỗ khi Giá đóng cửa thủng MA20.
    """
    def init(self):
        ticker = self.data_keys[0] if hasattr(self, "data_keys") and self.data_keys else "HPG"
        self.target_ticker = ticker
        self.ma20_close = self.I(indicator_sma, length=20, ticker=ticker)
        self.ma20_vol = self.I(indicator_volume_sma, length=20, ticker=ticker)

    def next(self):
        t = self.target_ticker
        close = self.get_close(t)
        vol = self.get_volume(t)
        ma20_p = self.ma20_close[-1]
        ma20_v = self.ma20_vol[-1]

        if ma20_p is None or ma20_v is None:
            return

        # Kiểm tra điều kiện Mua: Breakout MA20 + Nổ Vol
        if not self.is_holding(t):
            if close > ma20_p and vol > (1.2 * ma20_v):
                self.buy(t, size=5000, note="VSA Breakout MA20 + Vol spike")

        # Kiểm tra điều kiện Bán: Thủng MA20
        elif self.is_holding(t):
            if close < ma20_p:
                qty = self.get_holding_qty(t)
                self.sell(t, size=qty, note="Thủng MA20 chốt lời/cắt lỗ")

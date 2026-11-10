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
    """Chỉ báo sức mạnh tương đối (RSI 14)"""
    close = df[column]
    delta = close.diff()
    gain = pl.when(delta > 0).then(delta).otherwise(0.0)
    loss = pl.when(delta < 0).then(-delta).otherwise(0.0)

    avg_gain = gain.ewm_mean(span=length, adjust=False)
    avg_loss = loss.ewm_mean(span=length, adjust=False)

    rs = avg_gain / pl.when(avg_loss == 0).then(1e-10).otherwise(avg_loss)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi

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
        """Lấy số lượng cổ phiếu hiện đang nắm giữ trong danh mục"""
        # Kiểm tra qua engine broker portfolio
        if hasattr(self.engine, "broker") and hasattr(self.engine.broker, "positions"):
            pos = self.engine.broker.positions.get(ticker)
            if pos:
                return int(pos.shares if hasattr(pos, "shares") else getattr(pos, "quantity", 0))
        return 0

    def is_holding(self, ticker: str) -> bool:
        """Kiểm tra xem có đang giữ cổ phiếu này không"""
        return self.get_holding_qty(ticker) > 0

"""
Module Runner Điều phối Backtest (vn-backtest Engine Wrapper).
Nạp dữ liệu từ kho Parquet 5 năm, chuẩn hóa cột cho vn-backtest,
chạy mô phỏng khớp lệnh T+2.5 và tính toán toàn bộ Metrics định lượng.
"""

from pathlib import Path
from typing import Dict, List, Optional, Type, Union, Any
from datetime import date

import polars as pl
import vn_backtest as vb
from config import settings
from tools.parquet_manager import ParquetMarketDataManager

class BacktestRunner:
    """Cỗ máy thực thi Backtest chuẩn mực cho thị trường chứng khoán Việt Nam"""

    def __init__(
        self,
        initial_cash: float = settings.INITIAL_CAPITAL,
        buy_fee: float = settings.BROKER_FEE_RATE,
        sell_fee: float = settings.BROKER_FEE_RATE,
        sell_tax: float = settings.SELL_TAX_RATE,
        price_scale: float = 1.0  # Đặt 1.0 nếu giá là VND đầy đủ, hoặc 1000.0 nếu là nghìn đồng
    ):
        self.initial_cash = initial_cash
        self.buy_fee = buy_fee
        self.sell_fee = sell_fee
        self.sell_tax = sell_tax
        self.price_scale = price_scale
        self.parquet_mgr = ParquetMarketDataManager()
        self.reports_dir = settings.BASE_DIR / "dashboard" / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def prepare_data(self, tickers: Union[str, List[str]], days: int = 1250) -> Dict[str, pl.DataFrame]:
        """
        Chuẩn hóa dữ liệu từ kho Parquet sang định dạng vn-backtest yêu cầu:
        Cột bắt buộc: Date, Open, High, Low, Close, Volume
        """
        if isinstance(tickers, str):
            ticker_list = [tickers.upper()]
        else:
            ticker_list = [t.upper() for t in tickers]

        data_dict = {}
        for ticker in ticker_list:
            raw_df = self.parquet_mgr.get_ticker_history(ticker, days=days)
            if len(raw_df) == 0:
                print(f"⚠️ Không tìm thấy dữ liệu cho mã: {ticker}")
                continue

            # Đổi tên cột sang format vn-backtest
            df_formatted = raw_df.rename({
                "trade_date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume"
            })

            # Tự động phát hiện price_scale nếu giá ở dạng nghìn đồng (ví dụ HPG = 28.5 thay vì 28500)
            median_close = df_formatted["Close"].median()
            if median_close and median_close < 1000.0:
                self.price_scale = 1000.0

            data_dict[ticker] = df_formatted

        return data_dict

    def run(
        self,
        strategy_class: Type[vb.Strategy],
        tickers: Union[str, List[str]],
        days: int = 1250,
        strategy_name: Optional[str] = None,
        strategy_params: Optional[Dict[str, Any]] = None,
        generate_html_report: bool = True
    ) -> Dict[str, Any]:
        """
        Chạy Backtest đầy đủ:
        1. Nạp và chuẩn hóa dữ liệu
        2. Chạy BacktestEngine (Polars + Numba JIT)
        3. Tính toán toàn bộ chỉ số hiệu suất (PerformanceAnalyzer)
        4. Tự động xuất biểu đồ tương tác HTML (Plotly)
        """
        strat_name = strategy_name or strategy_class.__name__
        print(f"\n🚀 Khởi chạy Backtest: '{strat_name}' trên {days} phiên gần nhất...")

        # 1. Chuẩn bị dữ liệu
        data_dict = self.prepare_data(tickers, days=days)
        if not data_dict:
            raise ValueError("Không có dữ liệu hợp lệ để chạy backtest!")

        main_ticker = list(data_dict.keys())[0]

        # 2. Khởi tạo và chạy Engine
        engine = vb.BacktestEngine(
            data=data_dict,
            strategy_class=strategy_class,
            initial_cash=self.initial_cash,
            buy_fee=self.buy_fee,
            sell_fee=self.sell_fee,
            sell_tax=self.sell_tax,
            settlement_days=2,          # Chu kỳ T+2.5
            lot_size=100,               # Lô chẵn 100
            restrict_ceiling_buy=True,  # Không mua đuổi giá trần trắng bán
            restrict_floor_sell=True,   # Không bán tháo giá sàn trắng mua
            force_adjusted=True,        # Dữ liệu adj_price đã điều chỉnh
            price_scale=self.price_scale,
            strategy_params=strategy_params
        )

        raw_result = engine.run()

        # 3. Tính toán Metrics chi tiết
        metrics = vb.PerformanceAnalyzer.calculate_metrics(
            equity_curve=raw_result["equity_curve"],
            trades=raw_result["trades"],
            initial_cash=self.initial_cash
        )

        # 4. Xuất Báo cáo HTML/Plotly tương tác
        html_report_path = None
        html_filename = f"{strat_name.lower().replace(' ', '_')}.html"
        html_report_rel = f"dashboard/reports/{html_filename}"

        if generate_html_report:
            try:
                report_gen = vb.ReportGenerator()
                full_html_path = self.reports_dir / html_filename

                report_gen.generate_report(
                    metrics=metrics,
                    equity_curve=raw_result["equity_curve"],
                    trades=raw_result["trades"],
                    stock_data=data_dict,
                    ticker=main_ticker,
                    strategy_name=strat_name,
                    filename=str(full_html_path)
                )
                html_report_path = html_report_rel
                print(f"📊 Đã xuất biểu đồ tương tác: {html_report_rel}")
            except Exception as e:
                print(f"⚠️ Không thể xuất HTML report: {e}")

        return {
            "strategy_name": strat_name,
            "tickers": list(data_dict.keys()),
            "days": days,
            "metrics": metrics,
            "equity_curve": raw_result["equity_curve"],
            "trades": raw_result["trades"],
            "html_report_path": html_report_path,
            "html_filename": html_filename,
            "is_bankrupt": raw_result.get("is_bankrupt", False)
        }

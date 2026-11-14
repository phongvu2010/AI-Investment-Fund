"""
Module Runner Điều phối Backtest (vn-backtest Engine Wrapper).
Nạp dữ liệu từ kho Parquet 5 năm, chuẩn hóa cột cho vn-backtest,
chạy mô phỏng khớp lệnh T+2.5 và tính toán toàn bộ Metrics định lượng.
Tích hợp sẵn:
1. Quy chế khớp lệnh thực tế: T+2.5, lô 100, chặn mua trần (restrict_ceiling_buy), chặn bán sàn kẹt thanh khoản (restrict_floor_sell).
2. Tự động kiểm định Out-of-Sample (OOS) độc lập để ngăn chặn bẫy Overfitting (Học vẹt dữ liệu).
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

    def _evaluate_oos(
        self,
        strategy_class: Type[vb.Strategy],
        data_dict: Dict[str, pl.DataFrame],
        strategy_params: Optional[Dict[str, Any]] = None,
        oos_ratio: float = 0.25
    ) -> Dict[str, Any]:
        """Chia tách In-Sample / Out-of-Sample và đánh giá Overfitting độc lập"""
        in_sample = {}
        out_of_sample = {}
        for ticker, df in data_dict.items():
            n = len(df)
            split_idx = int(n * (1.0 - oos_ratio))
            in_sample[ticker] = df.slice(0, split_idx)
            out_of_sample[ticker] = df.slice(split_idx, n - split_idx)

        # Chạy In-Sample
        eng_is = vb.BacktestEngine(
            data=in_sample,
            strategy_class=strategy_class,
            initial_cash=self.initial_cash,
            buy_fee=self.buy_fee,
            sell_fee=self.sell_fee,
            sell_tax=self.sell_tax,
            settlement_days=2,
            lot_size=100,
            restrict_ceiling_buy=True,
            restrict_floor_sell=True,
            force_adjusted=True,
            price_scale=self.price_scale,
            strategy_params=strategy_params
        )
        res_is = eng_is.run()
        m_is = vb.PerformanceAnalyzer.calculate_metrics(res_is["equity_curve"], res_is["trades"], self.initial_cash)

        # Chạy Out-of-Sample
        eng_oos = vb.BacktestEngine(
            data=out_of_sample,
            strategy_class=strategy_class,
            initial_cash=self.initial_cash,
            buy_fee=self.buy_fee,
            sell_fee=self.sell_fee,
            sell_tax=self.sell_tax,
            settlement_days=2,
            lot_size=100,
            restrict_ceiling_buy=True,
            restrict_floor_sell=True,
            force_adjusted=True,
            price_scale=self.price_scale,
            strategy_params=strategy_params
        )
        res_oos = eng_oos.run()
        m_oos = vb.PerformanceAnalyzer.calculate_metrics(res_oos["equity_curve"], res_oos["trades"], self.initial_cash)

        is_sharpe = float(m_is.get("sharpe_ratio", 0.0))
        oos_sharpe = float(m_oos.get("sharpe_ratio", 0.0))
        is_mdd = abs(float(m_is.get("max_drawdown", 0.0))) * 100.0
        oos_mdd = abs(float(m_oos.get("max_drawdown", 0.0))) * 100.0

        if is_sharpe > 0:
            sharpe_retention = (oos_sharpe / is_sharpe) * 100.0
        else:
            sharpe_retention = 100.0 if oos_sharpe >= 0 else 0.0
        sharpe_decay = max(0.0, 100.0 - sharpe_retention)

        if oos_sharpe >= 0.80 and oos_mdd <= 18.0 and sharpe_retention >= 45.0:
            verdict = "ROBUST"
            status = "PASS"
            assessment = f"✅ Chiến lược ROBUST (Bền vững): Out-of-Sample Sharpe {oos_sharpe:.2f} duy trì {sharpe_retention:.1f}% hiệu suất In-Sample."
        elif oos_sharpe >= 0.50:
            verdict = "MODERATE_DECAY"
            status = "CAUTION"
            assessment = f"⚠️ Suy giảm vừa phải: Out-of-Sample Sharpe {oos_sharpe:.2f} suy giảm {sharpe_decay:.1f}% so với In-Sample."
        else:
            verdict = "OVERFITTED"
            status = "REJECTED"
            assessment = f"🚩 CẢNH BÁO BẪY OVERFITTING: Out-of-Sample Sharpe tụt xuống {oos_sharpe:.2f} (< 0.50) hoặc MDD tăng ({oos_mdd:.1f}%). Dấu hiệu học vẹt dữ liệu."

        return {
            "verdict": verdict,
            "status": status,
            "assessment": assessment,
            "in_sample": {
                "sharpe": is_sharpe, "cagr_pct": float(m_is.get("cagr", 0.0)) * 100.0,
                "mdd_pct": is_mdd, "win_rate_pct": float(m_is.get("win_rate", 0.0)) * 100.0,
                "total_trades": int(m_is.get("total_trades", 0))
            },
            "out_of_sample": {
                "sharpe": oos_sharpe, "cagr_pct": float(m_oos.get("cagr", 0.0)) * 100.0,
                "mdd_pct": oos_mdd, "win_rate_pct": float(m_oos.get("win_rate", 0.0)) * 100.0,
                "total_trades": int(m_oos.get("total_trades", 0))
            },
            "sharpe_retention_pct": round(sharpe_retention, 2),
            "sharpe_decay_pct": round(sharpe_decay, 2)
        }

    def run(
        self,
        strategy_class: Type[vb.Strategy],
        tickers: Union[str, List[str]],
        days: int = 1250,
        strategy_name: Optional[str] = None,
        strategy_params: Optional[Dict[str, Any]] = None,
        generate_html_report: bool = True,
        validate_oos: bool = True,
        oos_ratio: float = 0.25
    ) -> Dict[str, Any]:
        """
        Chạy Backtest đầy đủ:
        1. Nạp và chuẩn hóa dữ liệu
        2. Chạy BacktestEngine (Polars + Numba JIT) với cơ chế chặn mua trần / chặn bán sàn kẹt thanh khoản
        3. Tính toán toàn bộ chỉ số hiệu suất (PerformanceAnalyzer)
        4. Tự động kiểm định Chống Overfitting (In-Sample vs Out-of-Sample)
        5. Tự động xuất biểu đồ tương tác HTML (Plotly)
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
            restrict_floor_sell=True,   # Không bán tháo giá sàn trắng mua (Floor-Lock Guard)
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

        # 4. Kiểm định Out-of-Sample chống Overfitting nếu được yêu cầu
        overfit_report = None
        if validate_oos and days >= 100:
            try:
                overfit_report = self._evaluate_oos(
                    strategy_class=strategy_class,
                    data_dict=data_dict,
                    strategy_params=strategy_params,
                    oos_ratio=oos_ratio
                )
            except Exception as e:
                print(f"ℹ️ Không thể chạy kiểm định OOS ({e}). Tiếp tục với kết quả chuỗi đơn.")

        # 5. Xuất Báo cáo HTML/Plotly tương tác
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
            "overfit_report": overfit_report,
            "html_report_path": html_report_path,
            "html_filename": html_filename,
            "is_bankrupt": raw_result.get("is_bankrupt", False)
        }

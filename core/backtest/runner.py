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
from core.data.parquet_manager import ParquetMarketDataManager

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
        self.reports_dir = getattr(settings, "REPORTS_DIR", settings.BASE_DIR / "apps" / "api" / "static" / "reports")
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
        html_report_rel = f"apps/api/static/reports/{html_filename}"

        if generate_html_report:
            try:
                report_gen = vb.ReportGenerator(output_dir=str(self.reports_dir))
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

    def run_walk_forward_analysis(
        self,
        strategy_class: Type[vb.Strategy],
        tickers: Union[str, List[str]],
        days: int = 1250,
        n_splits: int = 4,
        train_ratio: float = 0.70,
        window_type: str = "rolling",
        strategy_name: Optional[str] = None,
        strategy_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Kiểm định Walk-Forward Analysis (WFA) chuẩn Quỹ Đầu Tư Định Lượng:
        1. Chia dữ liệu thành n_splits cửa sổ trượt liên tiếp (Rolling hoặc Expanding).
        2. Mỗi bước trượt đánh giá hiệu suất In-Sample (Huấn luyện) và Out-of-Sample (Kiểm định thực tế).
        3. Tính toán Hệ số Hiệu quả Walk-Forward (WFE), Độ ổn định (Consistency), và Phán quyết Độ bền vững cấp Quỹ.
        """
        strat_name = strategy_name or strategy_class.__name__
        print(f"\n🔬 Khởi chạy Walk-Forward Analysis (WFA): '{strat_name}' với {n_splits} folds ({window_type})...")

        data_dict = self.prepare_data(tickers, days=days)
        if not data_dict:
            raise ValueError("Không có dữ liệu hợp lệ để chạy Walk-Forward Analysis!")

        min_len = min(len(df) for df in data_dict.values())
        if min_len < 120:
            raise ValueError(f"Dữ liệu quá ngắn ({min_len} phiên), cần tối thiểu 120 phiên cho WFA.")

        k_splits = max(2, min(n_splits, 10))
        # Tỷ lệ IS/OOS
        tr = min(max(train_ratio, 0.50), 0.85)
        # Tính toán độ dài các phân đoạn
        # Cho rolling: IS_len + k_splits * OOS_len = min_len
        ratio_factor = tr / (1.0 - tr)
        oos_len = max(20, int(min_len / (ratio_factor + k_splits)))
        is_len = int(oos_len * ratio_factor)

        folds = []
        is_sharpes = []
        oos_sharpes = []
        is_cagrs = []
        oos_cagrs = []
        oos_mdds = []
        oos_win_rates = []
        all_oos_trades = []

        for k in range(k_splits):
            if window_type == "expanding":
                is_start = 0
                is_end = is_len + (k * oos_len)
            else:  # rolling
                is_start = k * oos_len
                is_end = is_start + is_len

            oos_start = is_end
            oos_end = min_len if k == k_splits - 1 else min(oos_start + oos_len, min_len)

            if oos_start >= oos_end:
                break

            # Cắt lát dữ liệu cho từng ticker
            is_data = {}
            oos_data = {}
            for ticker, df in data_dict.items():
                is_data[ticker] = df.slice(is_start, is_end - is_start)
                oos_data[ticker] = df.slice(oos_start, oos_end - oos_start)

            # Lấy chuỗi ngày
            first_ticker = list(data_dict.keys())[0]
            is_date_range = (
                str(is_data[first_ticker]["Date"][0]),
                str(is_data[first_ticker]["Date"][-1])
            )
            oos_date_range = (
                str(oos_data[first_ticker]["Date"][0]),
                str(oos_data[first_ticker]["Date"][-1])
            )

            # Chạy In-Sample
            eng_is = vb.BacktestEngine(
                data=is_data,
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
                data=oos_data,
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

            sh_is = float(m_is.get("sharpe_ratio", 0.0))
            sh_oos = float(m_oos.get("sharpe_ratio", 0.0))
            cagr_is = float(m_is.get("cagr", 0.0)) * 100.0
            cagr_oos = float(m_oos.get("cagr", 0.0)) * 100.0
            mdd_is = abs(float(m_is.get("max_drawdown", 0.0))) * 100.0
            mdd_oos = abs(float(m_oos.get("max_drawdown", 0.0))) * 100.0
            wr_is = float(m_is.get("win_rate", 0.0)) * 100.0
            wr_oos = float(m_oos.get("win_rate", 0.0)) * 100.0
            trades_is = int(m_is.get("total_trades", 0))
            trades_oos = int(m_oos.get("total_trades", 0))

            is_sharpes.append(sh_is)
            oos_sharpes.append(sh_oos)
            is_cagrs.append(cagr_is)
            oos_cagrs.append(cagr_oos)
            oos_mdds.append(mdd_oos)
            oos_win_rates.append(wr_oos)
            all_oos_trades.extend(res_oos.get("trades", []))

            # Độ suy giảm Sharpe của từng fold
            retention = (sh_oos / sh_is * 100.0) if sh_is > 0 else (100.0 if sh_oos >= 0 else 0.0)

            folds.append({
                "fold": k + 1,
                "is_date_range": is_date_range,
                "oos_date_range": oos_date_range,
                "is_bars": len(is_data[first_ticker]),
                "oos_bars": len(oos_data[first_ticker]),
                "in_sample": {
                    "sharpe": round(sh_is, 2), "cagr_pct": round(cagr_is, 2),
                    "mdd_pct": round(mdd_is, 2), "win_rate_pct": round(wr_is, 1),
                    "total_trades": trades_is
                },
                "out_of_sample": {
                    "sharpe": round(sh_oos, 2), "cagr_pct": round(cagr_oos, 2),
                    "mdd_pct": round(mdd_oos, 2), "win_rate_pct": round(wr_oos, 1),
                    "total_trades": trades_oos
                },
                "sharpe_retention_pct": round(retention, 1)
            })

        # Tổng hợp các chỉ số WFA
        actual_folds = len(folds)
        avg_is_sharpe = sum(is_sharpes) / actual_folds if actual_folds > 0 else 0.0
        avg_oos_sharpe = sum(oos_sharpes) / actual_folds if actual_folds > 0 else 0.0
        avg_is_cagr = sum(is_cagrs) / actual_folds if actual_folds > 0 else 0.0
        avg_oos_cagr = sum(oos_cagrs) / actual_folds if actual_folds > 0 else 0.0
        avg_oos_mdd = sum(oos_mdds) / actual_folds if actual_folds > 0 else 0.0
        avg_oos_win_rate = sum(oos_win_rates) / actual_folds if actual_folds > 0 else 0.0

        # Walk-Forward Efficiency (WFE)
        if avg_is_sharpe > 0:
            wfe_sharpe = (avg_oos_sharpe / avg_is_sharpe) * 100.0
        else:
            wfe_sharpe = 100.0 if avg_oos_sharpe >= 0 else 0.0

        if avg_is_cagr > 0:
            wfe_cagr = (avg_oos_cagr / avg_is_cagr) * 100.0
        else:
            wfe_cagr = 100.0 if avg_oos_cagr >= 0 else 0.0

        profitable_folds = sum(1 for c in oos_cagrs if c > 0)
        profitable_folds_pct = (profitable_folds / actual_folds * 100.0) if actual_folds > 0 else 0.0
        robust_folds = sum(1 for s in oos_sharpes if s >= 0.50)
        consistency_pct = (robust_folds / actual_folds * 100.0) if actual_folds > 0 else 0.0

        # Phán quyết Độ bền vững (Verdict)
        if wfe_sharpe >= 50.0 and avg_oos_sharpe >= 0.80 and profitable_folds_pct >= 75.0:
            verdict = "INSTITUTIONAL_ROBUST"
            status = "PASS"
            assessment = (
                f"🏆 ĐẠT CHUẨN CẤP QUỸ (INSTITUTIONAL ROBUST): WFE Sharpe đạt {wfe_sharpe:.1f}%, "
                f"Sharpe OOS trung bình {avg_oos_sharpe:.2f}, {profitable_folds}/{actual_folds} chu kỳ OOS sinh lời dương."
            )
        elif wfe_sharpe >= 35.0 and avg_oos_sharpe >= 0.50 and profitable_folds_pct >= 50.0:
            verdict = "ACCEPTABLE_ROBUST"
            status = "CAUTION"
            assessment = (
                f"✅ ĐẠT ĐỘ BỀN CHẤP NHẬN ĐƯỢC: WFE Sharpe {wfe_sharpe:.1f}%, Sharpe OOS {avg_oos_sharpe:.2f}. "
                f"Chiến lược giữ được hiệu suất khả quan qua các lát cắt trượt."
            )
        else:
            verdict = "FRAGILE_OVERFIT"
            status = "REJECTED"
            assessment = (
                f"🚩 CẢNH BÁO BẪY OVERFIT: WFE Sharpe sụt giảm ({wfe_sharpe:.1f}%), Sharpe OOS ({avg_oos_sharpe:.2f}) "
                f"hoặc chỉ có {profitable_folds}/{actual_folds} chu kỳ OOS có lãi. Chiến lược không chịu được kiểm định trượt."
            )

        return {
            "strategy_name": strat_name,
            "tickers": list(data_dict.keys()),
            "window_type": window_type,
            "n_splits": actual_folds,
            "verdict": verdict,
            "status": status,
            "assessment": assessment,
            "summary": {
                "wfe_sharpe_pct": round(wfe_sharpe, 2),
                "wfe_cagr_pct": round(wfe_cagr, 2),
                "avg_is_sharpe": round(avg_is_sharpe, 2),
                "avg_oos_sharpe": round(avg_oos_sharpe, 2),
                "avg_is_cagr_pct": round(avg_is_cagr, 2),
                "avg_oos_cagr_pct": round(avg_oos_cagr, 2),
                "avg_oos_mdd_pct": round(avg_oos_mdd, 2),
                "avg_oos_win_rate_pct": round(avg_oos_win_rate, 1),
                "consistency_pct": round(consistency_pct, 1),
                "profitable_folds_pct": round(profitable_folds_pct, 1),
                "profitable_folds": profitable_folds,
                "total_folds": actual_folds
            },
            "folds": folds,
            "total_oos_trades": len(all_oos_trades)
        }

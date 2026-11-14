"""
Module Chuyển đổi Báo cáo (Report Adapter).
Nhận kết quả từ vn-backtest và tự động biên tập thành:
1. Báo cáo Markdown (backtest_report.md) chuẩn mực cho AI Agent đọc hiểu
2. Bảng thẩm định độc lập của Giám đốc Rủi ro (CRO Evaluation)
3. Thẩm định Chống Overfitting Độc Lập (In-Sample vs Out-of-Sample Guard)
"""

from pathlib import Path
from typing import Dict, Any, Optional

class BacktestReportAdapter:
    """Lớp chuyển đổi và thẩm định kết quả backtest của Quỹ"""

    @staticmethod
    def evaluate_cro_rules(metrics: Dict[str, Any], overfit_report: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Thẩm định theo bộ quy tắc rủi ro của Quỹ và Hạn chế Overfitting:
        - Sharpe >= 1.2
        - Max Drawdown <= 15.0%
        - Profit Factor >= 1.8
        - Total Trades >= 15
        - [QUY TẮC MỚI] Anti-Overfitting Guard: Out-of-Sample Sharpe >= 0.50 & không bị bác bỏ do học vẹt.
        """
        sharpe = metrics.get("sharpe_ratio", 0.0)
        mdd = abs(metrics.get("max_drawdown", 0.0)) * 100.0  # Chuyển thành % dương
        profit_factor = metrics.get("profit_factor", 0.0)
        win_rate = metrics.get("win_rate", 0.0) * 100.0
        total_trades = metrics.get("total_trades", 0)
        cagr = metrics.get("cagr", 0.0) * 100.0

        # Tiêu chuẩn thẩm định cơ bản
        check_sharpe = sharpe >= 1.2
        check_mdd = mdd <= 15.0
        check_pf = profit_factor >= 1.8
        check_trades = total_trades >= 15  # Đảm bảo đủ số mẫu thống kê

        # Tiêu chuẩn thẩm định chống Overfitting (Out-of-Sample Verification)
        check_overfit = True
        overfit_msg = "Chưa kích hoạt Out-of-Sample (Kiểm thử đơn chuỗi)"
        if overfit_report:
            verdict_of = overfit_report.get("verdict", "UNKNOWN")
            status_of = overfit_report.get("status", "PASS")
            retention_pct = overfit_report.get("sharpe_retention_pct", 100.0)
            oos_sharpe = overfit_report.get("out_of_sample", {}).get("sharpe", 0.0)
            oos_mdd = overfit_report.get("out_of_sample", {}).get("mdd_pct", 0.0)

            if status_of == "REJECTED" or verdict_of == "OVERFITTED" or oos_sharpe < 0.50 or oos_mdd > 20.0:
                check_overfit = False
                overfit_msg = f"THẤT BẠI: Out-of-Sample Sharpe sụt giảm mạnh ({oos_sharpe:.2f} < 0.50) hoặc MDD tăng ({oos_mdd:.1f}%). Dấu hiệu học vẹt dữ liệu."
            else:
                check_overfit = True
                overfit_msg = f"ĐẠT CHUẨN: Out-of-Sample Sharpe = {oos_sharpe:.2f} (Giữ vững {retention_pct:.1f}% hiệu suất In-Sample)"

        passed_all = check_sharpe and check_mdd and check_pf and check_trades and check_overfit

        if not check_overfit:
            status = "REJECTED"
            verdict = "CHIẾN LƯỢC BỊ TỪ CHỐI (Vi phạm Hiến pháp Quỹ: BẪY OVERFITTING / Học vẹt dữ liệu quá khứ)"
        elif passed_all:
            status = "APPROVED_TIER_A"
            verdict = "CHIẾN LƯỢC ĐẠT CHUẨN LOẠI A (Cấp phép hoạt động, phân bổ tối đa 25% NAV)"
        elif check_mdd and sharpe >= 0.9 and check_overfit:
            status = "APPROVED_TIER_B"
            verdict = "CHIẾN LƯỢC ĐẠT CHUẨN LOẠI B (Cần theo dõi thêm, phân bổ tối đa 10% NAV)"
        else:
            status = "REJECTED"
            verdict = "CHIẾN LƯỢC BỊ TỪ CHỐI (Không đạt tiêu chuẩn kiểm soát rủi ro của Quỹ)"

        return {
            "status": status,
            "verdict": verdict,
            "check_sharpe": (check_sharpe, f"Sharpe = {sharpe:.2f} (Yêu cầu >= 1.20)"),
            "check_mdd": (check_mdd, f"Max Drawdown = {mdd:.2f}% (Yêu cầu <= 15.00%)"),
            "check_pf": (check_pf, f"Profit Factor = {profit_factor:.2f} (Yêu cầu >= 1.80)"),
            "check_trades": (check_trades, f"Tổng số lệnh = {total_trades} (Yêu cầu >= 15 lệnh)"),
            "check_overfit": (check_overfit, overfit_msg),
            "cagr_pct": cagr,
            "win_rate_pct": win_rate,
            "mdd_pct": mdd,
            "sharpe": sharpe,
            "profit_factor": profit_factor,
            "overfit_report": overfit_report
        }

    @classmethod
    def generate_markdown_report(cls, backtest_result: Dict[str, Any], output_path: Optional[Path] = None) -> str:
        """Sinh file Markdown chuẩn hóa để AI Agent đọc và hiểu 100%"""
        strat_name = backtest_result["strategy_name"]
        tickers = ", ".join(backtest_result["tickers"])
        metrics = backtest_result["metrics"]
        overfit_report = backtest_result.get("overfit_report")
        cro_eval = cls.evaluate_cro_rules(metrics, overfit_report=overfit_report)

        total_return_pct = (metrics.get("total_return") or 0.0) * 100.0
        cagr_pct = (metrics.get("cagr") or 0.0) * 100.0
        mdd_pct = abs(metrics.get("max_drawdown") or 0.0) * 100.0
        sharpe = metrics.get("sharpe_ratio") or 0.0
        sortino = metrics.get("sortino_ratio") or 0.0
        calmar = metrics.get("calmar_ratio") or 0.0
        win_rate_pct = (metrics.get("win_rate") or 0.0) * 100.0
        profit_factor = metrics.get("profit_factor") or 0.0
        total_trades = metrics.get("total_trades") or 0
        avg_trade_return_pct = (metrics.get("avg_trade_return") or 0.0) * 100.0
        avg_hold_days = metrics.get("avg_hold_days") or 0.0
        html_report_path = backtest_result.get("html_report_path", "")
        html_filename = backtest_result.get("html_filename", Path(html_report_path).name if html_report_path else "")

        overfit_section = ""
        if overfit_report:
            is_m = overfit_report.get("in_sample", {})
            oos_m = overfit_report.get("out_of_sample", {})
            retention = overfit_report.get("sharpe_retention_pct", 0.0)
            decay = overfit_report.get("sharpe_decay_pct", 0.0)
            overfit_section = f"""
---

## 3. THẨM ĐỊNH CHỐNG OVERFITTING (OUT-OF-SAMPLE VERIFICATION)

| Chỉ số Đối sánh | Tập Huấn Luyện (In-Sample 70%) | Tập Kiểm Định (Out-of-Sample 30%) | Nhận định |
| :--- | :---: | :---: | :--- |
| **Tỷ số Sharpe** | **{is_m.get('sharpe', 0.0):.2f}** | **{oos_m.get('sharpe', 0.0):.2f}** | Giữ vững **{retention:.1f}%** (Suy giảm: {decay:.1f}%) |
| **Max Drawdown** | **-{is_m.get('mdd_pct', 0.0):.2f}%** | **-{oos_m.get('mdd_pct', 0.0):.2f}%** | Rủi ro sụt giảm thực tế |
| **Tỷ lệ Thắng** | **{is_m.get('win_rate_pct', 0.0):.1f}%** | **{oos_m.get('win_rate_pct', 0.0):.1f}%** | Tỷ lệ thắng độc lập |
| **Số Lệnh Khớp** | **{is_m.get('total_trades', 0)} lệnh** | **{oos_m.get('total_trades', 0)} lệnh** | Mẫu kiểm chứng |

> **Phán Quyết Chống Overfitting:** `[{overfit_report.get('verdict', 'UNKNOWN')}]` — {overfit_report.get('assessment', '')}
"""

        md_content = f"""# BÁO CÁO THẨM ĐỊNH CHIẾN LƯỢC ĐẦU TƯ: {strat_name.upper()}
* **Mã cổ phiếu áp dụng:** `{tickers}`
* **Thời gian kiểm nghiệm:** `{metrics.get('years', 0):.1f} năm` ({metrics.get('duration_days', 0)} ngày giao dịch)
* **Vốn khởi điểm giả lập:** `{metrics.get('initial_cash', 0):,.0f} VND`
* **Vốn kết thúc (Equity):** `{metrics.get('final_equity', 0):,.0f} VND`
* **Biểu đồ tương tác HTML:** [dashboard/reports/{html_filename}](../../../dashboard/reports/{html_filename})

---

## 1. BẢNG CHỈ SỐ ĐỊNH LƯỢNG (QUANTITATIVE METRICS)

| Chỉ số Hiệu suất | Giá trị Thực tế | Đánh giá Chuẩn mực |
| :--- | :---: | :--- |
| **Tổng Lợi Nhuận (Total Return)** | **{total_return_pct:+.2f}%** | Lợi nhuận gộp toàn chu kỳ |
| **Lợi nhuận Bình quân Năm (CAGR)** | **{cagr_pct:+.2f}%/năm** | Tỷ suất sinh lời kép hàng năm |
| **Mức Sụt Giảm Tối Đa (Max Drawdown)** | **-{mdd_pct:.2f}%** | Rủi ro sụt giảm vốn từ đỉnh |
| **Sharpe Ratio (Rủi ro tổng thể)** | **{sharpe:.2f}** | Đo lường tỷ suất trên biến động |
| **Sortino Ratio (Rủi ro sụt giảm)** | **{sortino:.2f}** | Chỉ tính biến động chiều giảm |
| **Calmar Ratio** | **{calmar:.2f}** | Tỷ lệ CAGR / Max Drawdown |
| **Tỷ lệ Thắng (Win Rate)** | **{win_rate_pct:.1f}%** | % Lệnh có lợi nhuận dương |
| **Hệ số Lợi nhuận/Lỗ (Profit Factor)**| **{profit_factor:.2f}** | Tổng tiền thắng / Tổng tiền thua |
| **Tổng Số Lệnh Khớp (Total Trades)**| **{total_trades} lệnh** | Độ tin cậy mẫu thống kê |
| **Lãi Trung Bình Mỗi Lệnh** | **{avg_trade_return_pct:+.2f}%** | Kỳ vọng sinh lời trung bình/deal |
| **Thời Gian Nắm Giữ Trung Bình** | **{avg_hold_days:.1f} ngày** | Chu kỳ nắm giữ vị thế ($T+2.5$) |

---

## 2. KẾT LUẬN THẨM ĐỊNH CỦA GIÁM ĐỐC RỦI RO (CRO EVALUATION)

### 📋 Bảng Đối chiếu Kỷ luật Quỹ:
* {'✅ ĐẠT' if cro_eval['check_sharpe'][0] else '❌ KHÔNG ĐẠT'}: {cro_eval['check_sharpe'][1]}
* {'✅ ĐẠT' if cro_eval['check_mdd'][0] else '❌ KHÔNG ĐẠT'}: {cro_eval['check_mdd'][1]}
* {'✅ ĐẠT' if cro_eval['check_pf'][0] else '❌ KHÔNG ĐẠT'}: {cro_eval['check_pf'][1]}
* {'✅ ĐẠT' if cro_eval['check_trades'][0] else '❌ KHÔNG ĐẠT'}: {cro_eval['check_trades'][1]}
* {'✅ ĐẠT' if cro_eval['check_overfit'][0] else '❌ KHÔNG ĐẠT'}: {cro_eval['check_overfit'][1]}

### ⚖️ PHÁN QUYẾT CUỐI CÙNG:
> **{cro_eval['verdict']}**
{overfit_section}
"""

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"📄 Đã xuất báo cáo thẩm định Markdown: {output_path}")

        return md_content

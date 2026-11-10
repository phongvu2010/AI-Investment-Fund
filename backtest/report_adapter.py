"""
Module Chuyển đổi Báo cáo (Report Adapter).
Nhận kết quả từ vn-backtest và tự động biên tập thành:
1. Báo cáo Markdown (backtest_report.md) chuẩn mực cho AI Agent đọc hiểu
2. Bảng thẩm định độc lập của Giám đốc Rủi ro (CRO Evaluation)
"""

from pathlib import Path
from typing import Dict, Any, Optional

class BacktestReportAdapter:
    """Lớp chuyển đổi và thẩm định kết quả backtest của Quỹ"""

    @staticmethod
    def evaluate_cro_rules(metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Thẩm định theo bộ quy tắc rủi ro của Quỹ"""
        sharpe = metrics.get("sharpe_ratio", 0.0)
        mdd = abs(metrics.get("max_drawdown", 0.0)) * 100.0  # Chuyển thành % dương
        profit_factor = metrics.get("profit_factor", 0.0)
        win_rate = metrics.get("win_rate", 0.0) * 100.0
        total_trades = metrics.get("total_trades", 0)
        cagr = metrics.get("cagr", 0.0) * 100.0

        # Tiêu chuẩn thẩm định
        check_sharpe = sharpe >= 1.2
        check_mdd = mdd <= 15.0
        check_pf = profit_factor >= 1.8
        check_trades = total_trades >= 15  # Đảm bảo đủ số mẫu thống kê

        passed_all = check_sharpe and check_mdd and check_pf and check_trades

        if passed_all:
            status = "APPROVED_TIER_A"
            verdict = "CHIẾN LƯỢC ĐẠT CHUẨN LOẠI A (Cấp phép hoạt động, phân bổ tối đa 25% NAV)"
        elif check_mdd and sharpe >= 0.9:
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
            "cagr_pct": cagr,
            "win_rate_pct": win_rate,
            "mdd_pct": mdd,
            "sharpe": sharpe,
            "profit_factor": profit_factor
        }

    @classmethod
    def generate_markdown_report(cls, backtest_result: Dict[str, Any], output_path: Optional[Path] = None) -> str:
        """Sinh file Markdown chuẩn hóa để AI Agent đọc và hiểu 100%"""
        strat_name = backtest_result["strategy_name"]
        tickers = ", ".join(backtest_result["tickers"])
        metrics = backtest_result["metrics"]
        cro_eval = cls.evaluate_cro_rules(metrics)

        total_return_pct = metrics.get("total_return", 0.0) * 100.0
        cagr_pct = metrics.get("cagr", 0.0) * 100.0
        mdd_pct = abs(metrics.get("max_drawdown", 0.0)) * 100.0
        sharpe = metrics.get("sharpe_ratio", 0.0)
        sortino = metrics.get("sortino_ratio", 0.0)
        calmar = metrics.get("calmar_ratio", 0.0)
        win_rate_pct = metrics.get("win_rate", 0.0) * 100.0
        profit_factor = metrics.get("profit_factor", 0.0)
        total_trades = metrics.get("total_trades", 0)
        avg_trade_return_pct = metrics.get("avg_trade_return", 0.0) * 100.0
        avg_hold_days = metrics.get("avg_hold_days", 0.0)
        html_report_path = backtest_result.get("html_report_path", "")

        md_content = f"""# BÁO CÁO THẨM ĐỊNH CHIẾN LƯỢC ĐẦU TƯ: {strat_name.upper()}
* **Mã cổ phiếu áp dụng:** `{tickers}`
* **Thời gian kiểm nghiệm:** `{metrics.get('years', 0):.1f} năm` ({metrics.get('duration_days', 0)} ngày giao dịch)
* **Vốn khởi điểm giả lập:** `{metrics.get('initial_cash', 0):,.0f} VND`
* **Vốn kết thúc (Equity):** `{metrics.get('final_equity', 0):,.0f} VND`
* **Biểu đồ tương tác HTML:** `{html_report_path}`

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

###  Bảng Đối chiếu Kỷ luật Quỹ:
* {'✅ ĐẠT' if cro_eval['check_sharpe'][0] else '❌ KHÔNG ĐẠT'}: {cro_eval['check_sharpe'][1]}
* {'✅ ĐẠT' if cro_eval['check_mdd'][0] else '❌ KHÔNG ĐẠT'}: {cro_eval['check_mdd'][1]}
* {'✅ ĐẠT' if cro_eval['check_pf'][0] else '❌ KHÔNG ĐẠT'}: {cro_eval['check_pf'][1]}
* {'✅ ĐẠT' if cro_eval['check_trades'][0] else '❌ KHÔNG ĐẠT'}: {cro_eval['check_trades'][1]}

### ⚖️ PHÁN QUYẾT CUỐI CÙNG:
> **{cro_eval['verdict']}**
"""

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"📄 Đã xuất báo cáo thẩm định Markdown: {output_path}")

        return md_content

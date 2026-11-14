"""
Harness Verification Loop (Code-Backed Self-Correction).
Bọc quanh tools/strategy_generator.py (StrategySkillPackage).
Khi Agent sinh code chiến lược mới kế thừa BaseFundStrategy, Harness tự động:
1. Chạy BacktestRunner.run(..., validate_oos=True) độc lập (In-Sample vs Out-of-Sample).
2. Nếu cro_eval["status"] == "REJECTED" HOẶC overfit_report["verdict"] == "OVERFITTED":
   - Harness tự động kích hoạt StrategyOptimizerEngine tối đa 2 vòng lặp để tinh chỉnh tham số.
   - Tự động ghi biên bản khám nghiệm Post-Mortem vào .agent/journals/.
3. Trả về kết quả hoàn chỉnh, minh bạch cho CEO.
"""

from pathlib import Path
from typing import Dict, Any, Type, List, Optional, Union
from datetime import datetime
import json
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import vn_backtest as vb
from config import settings
from backtest.runner import BacktestRunner
from backtest.report_adapter import BacktestReportAdapter
from tools.strategy_generator import StrategySkillPackage
from tools.strategy_optimizer import StrategyOptimizerEngine


class HarnessVerificationLoop:
    """Vòng lặp Kiểm định & Tự sửa chữa Mã Chiến lược (Verification & Self-Correction Loop)"""

    def __init__(self):
        self.runner = BacktestRunner(initial_cash=settings.INITIAL_CAPITAL)
        self.optimizer = StrategyOptimizerEngine()
        self.journals_dir = settings.BASE_DIR / ".agent" / "journals"
        self.journals_dir.mkdir(parents=True, exist_ok=True)

    def write_post_mortem_journal(
        self,
        strategy_id: str,
        strategy_title: str,
        iteration: int,
        cro_eval: Dict[str, Any],
        overfit_report: Optional[Dict[str, Any]],
        remedy_summary: str
    ) -> Path:
        """Ghi biên bản Khám nghiệm & Bài học Thể chế vào .agent/journals/"""
        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        date_str = now.strftime("%Y-%m-%d %H:%M:%S")
        journal_path = self.journals_dir / f"post_mortem_{strategy_id}_{timestamp_str}.md"

        overfit_verdict = overfit_report.get("verdict", "N/A") if overfit_report else "N/A"
        overfit_assess = overfit_report.get("assessment", "Không có dữ liệu OOS") if overfit_report else "N/A"

        content = f"""# NHẬT KÝ KHÁM NGHIỆM CHIẾN LƯỢC - HARNESS VERIFICATION LOOP
* **Thời điểm ghi nhận:** `{date_str}`
* **Chiến lược:** `{strategy_title}` (`strategy-{strategy_id}`)
* **Vòng kiểm định:** `Iteration #{iteration}`
* **Người thực thi:** `Antigravity Harness Verification Loop & CRO Auditor`

---

## 1. PHÁN QUYẾT KIỂM ĐỊNH BAN ĐẦU
* **Trạng thái CRO:** `{cro_eval.get('status', 'REJECTED')}` - {cro_eval.get('verdict', 'BỊ TỪ CHỐI')}
* **Tỷ số Sharpe:** `{cro_eval.get('sharpe', 0.0):.2f}` (Yêu cầu >= 1.20)
* **Max Drawdown:** `{cro_eval.get('mdd_pct', 0.0):.2f}%` (Yêu cầu <= 15.0%)
* **CAGR:** `{cro_eval.get('cagr_pct', 0.0):+.2f}%/năm`
* **Tỷ lệ Thắng:** `{cro_eval.get('win_rate_pct', 0.0):.1f}%`
* **Kiểm định Out-of-Sample (OOS):** `{overfit_verdict}`
* **Đánh giá OOS:** {overfit_assess}

---

## 2. CHẨN ĐOÁN LỖI & NGUYÊN NHÂN GỐC RỄ
Chiến lược không vượt qua rào chắn rủi ro hoặc xuất hiện dấu hiệu học vẹt dữ liệu (Overfitting).
Harness đã kích hoạt cơ chế Code-Backed Self-Correction nhằm tái cấu trúc tham số thích ứng.

---

## 3. BIỆN PHÁP KHẮC PHỤC (SELF-CORRECTION APPLIED)
{remedy_summary}

---

## 4. BÀI HỌC THỂ CHẾ CHO HỆ THỐNG
1. Tuyệt đối không đưa chiến lược có Sharpe Out-of-Sample suy giảm nghiêm trọng vào vận hành thực tế.
2. Mọi chiến lược mới bắt buộc phải trải qua ít nhất 1 chu kỳ kiểm định OOS và hiệu chỉnh tham số tự động.
"""
        journal_path.write_text(content, encoding="utf-8")
        return journal_path

    def deploy_verify_and_heal(
        self,
        strategy_class: Type[vb.Strategy],
        strategy_id: str,
        strategy_title: str,
        tickers: Union[str, List[str]],
        description: str,
        entry_rules: str,
        exit_rules: str,
        days: int = 1250,
        strategy_params: Optional[Dict[str, Any]] = None,
        max_heal_loops: int = 2
    ) -> Dict[str, Any]:
        """
        Quy trình Toàn diện có Bảo vệ & Tự Khắc Phục (Self-Correction Pipeline):
        1. Đóng gói & Chạy Backtest với kiểm định OOS
        2. Nếu REJECTED hoặc OVERFITTED: Kích hoạt Self-Healing vòng lặp (tối đa max_heal_loops)
        3. Ghi chép Post-Mortem đầy đủ
        4. Trả kết quả cuối cùng
        """
        package = StrategySkillPackage(strategy_id=strategy_id, strategy_title=strategy_title)

        # Vòng kiểm định ban đầu
        current_params = dict(strategy_params or {})
        current_class = strategy_class
        main_ticker = tickers if isinstance(tickers, str) else tickers[0]

        iteration = 1
        heal_history = []

        # Chạy kiểm định lần đầu
        res = self.runner.run(
            strategy_class=current_class,
            tickers=tickers,
            days=days,
            strategy_name=strategy_title,
            strategy_params=current_params,
            generate_html_report=True,
            validate_oos=True
        )

        cro_eval = BacktestReportAdapter.evaluate_cro_rules(res["metrics"])
        overfit_report = res.get("overfit_report") or {}

        needs_healing = (
            cro_eval.get("status") == "REJECTED" or
            overfit_report.get("verdict") == "OVERFITTED"
        )

        while needs_healing and iteration <= max_heal_loops:
            print(f"\n⚠️ [HARNESS SELF-HEALING] Vòng lặp #{iteration}: Chiến lược chưa đạt chuẩn ({cro_eval.get('status')}, OOS: {overfit_report.get('verdict')}).")
            print("🔧 Đang kích hoạt StrategyOptimizerEngine để tự động tối ưu hóa tham số...")

            remedy_info = f"- Tự động tinh chỉnh không gian tham số vòng #{iteration} để khắc phục sụt giảm hiệu suất."
            if "vsa" in strategy_id.lower() or "momentum" in strategy_id.lower():
                try:
                    heal_res = self.optimizer.auto_heal_vsa_strategy(ticker=main_ticker)
                    best_cand = heal_res.get("best_candidate") or {}
                    if best_cand.get("params"):
                        current_params.update(best_cand["params"])
                        remedy_info = f"- Đã áp dụng bộ tham số tối ưu từ Grid Search: {best_cand['params']}"
                except Exception as e:
                    remedy_info = f"- Lỗi khi chạy auto-heal: {e}. Áp dụng tham số thận trọng mặc định."
                    current_params.update({"vol_mult": 0.8, "rsi_period": 14})
            else:
                current_params.update({"vol_mult": 0.8, "stop_loss_pct": 0.05})

            # Ghi Post-Mortem
            journal_path = self.write_post_mortem_journal(
                strategy_id=strategy_id,
                strategy_title=strategy_title,
                iteration=iteration,
                cro_eval=cro_eval,
                overfit_report=overfit_report,
                remedy_summary=remedy_info
            )
            heal_history.append({
                "iteration": iteration,
                "journal": str(journal_path),
                "params_tried": dict(current_params),
                "prev_status": cro_eval.get("status")
            })

            # Chạy lại Backtest với tham số mới
            iteration += 1
            res = self.runner.run(
                strategy_class=current_class,
                tickers=tickers,
                days=days,
                strategy_name=strategy_title,
                strategy_params=current_params,
                generate_html_report=True,
                validate_oos=True
            )
            cro_eval = BacktestReportAdapter.evaluate_cro_rules(res["metrics"])
            overfit_report = res.get("overfit_report") or {}
            needs_healing = (
                cro_eval.get("status") == "REJECTED" or
                overfit_report.get("verdict") == "OVERFITTED"
            )

        # Xuất Báo cáo và Đóng gói Skill cuối cùng
        deploy_res = package.deploy_and_backtest(
            strategy_class=current_class,
            tickers=tickers,
            description=description,
            entry_rules=entry_rules,
            exit_rules=exit_rules,
            days=days,
            strategy_params=current_params
        )

        deploy_res["verification_loop"] = {
            "total_iterations": iteration,
            "heal_history": heal_history,
            "final_cro_status": cro_eval.get("status"),
            "final_overfit_verdict": overfit_report.get("verdict"),
            "final_params": current_params
        }

        return deploy_res

"""
Module Tự động hóa Khởi tạo & Kiểm định Chiến lược (Strategy Generator).
Tự động đóng gói một ý tưởng chiến lược thành:
1. Thư mục Skill (.agent/skills/strategy-<name>/)
2. Mã nguồn strategy.py (chuẩn vn-backtest)
3. Tài liệu nghiệp vụ SKILL.md
4. Tự động kích hoạt BacktestRunner 5 năm
5. Tự động xuất Báo cáo Thẩm định backtest_report.md & Biểu đồ Plotly
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, Type, List, Optional, Union

# Tự động thêm thư mục gốc dự án vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings
from core.backtest.runner import BacktestRunner
from core.backtest.report_adapter import BacktestReportAdapter
import vn_backtest as vb

class StrategySkillPackage:
    """Đóng gói và triển khai một Skill chiến lược vào hệ thống Quỹ"""

    def __init__(self, strategy_id: str, strategy_title: str):
        self.strategy_id = strategy_id.lower().replace("_", "-")
        self.strategy_title = strategy_title
        self.skill_dir = settings.BASE_DIR / ".agent" / "skills" / f"strategy-{self.strategy_id}"
        self.skill_dir.mkdir(parents=True, exist_ok=True)

    def deploy_and_backtest(
        self,
        strategy_class: Type[vb.Strategy],
        tickers: Union[str, List[str]],
        description: str,
        entry_rules: str,
        exit_rules: str,
        days: int = 1250,
        strategy_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Quy trình trọn gói:
        1. Chạy Backtest 5 năm với vn-backtest
        2. Tạo SKILL.md
        3. Tạo backtest_report.md
        4. Cập nhật status.json
        """
        print(f"\n📦 Bắt đầu đóng gói Skill: strategy-{self.strategy_id}...")

        # 1. Chạy Backtest
        runner = BacktestRunner(initial_cash=settings.INITIAL_CAPITAL)
        result = runner.run(
            strategy_class=strategy_class,
            tickers=tickers,
            days=days,
            strategy_name=self.strategy_title,
            strategy_params=strategy_params,
            generate_html_report=True
        )

        # 2. Xuất Báo cáo Thẩm định Markdown
        report_md_path = self.skill_dir / "backtest_report.md"
        report_md_content = BacktestReportAdapter.generate_markdown_report(result, output_path=report_md_path)

        # 3. Thẩm định Hội đồng CRO
        cro_eval = BacktestReportAdapter.evaluate_cro_rules(result["metrics"])

        # 4. Tạo file SKILL.md chuẩn mực cho AI Agent
        skill_md_path = self.skill_dir / "SKILL.md"
        skill_md_content = f"""---
name: strategy-{self.strategy_id}
description: >-
  Chiến lược {self.strategy_title}.
  Trạng thái: {cro_eval['status']}.
  Sử dụng skill này khi cần phân tích tín hiệu vào/ra lệnh cho các mã: {tickers}.
---

# CHIẾN LƯỢC: {self.strategy_title.upper()}

## 1. MÔ TẢ TỔNG QUAN
{description}

## 2. QUY TẮC VÀO LỆNH (ENTRY RULES)
{entry_rules}

## 3. QUY TẮC THOÁT LỆNH & CẮT LỖ (EXIT RULES)
{exit_rules}

## 4. KẾT QUẢ THẨM ĐỊNH LỊCH SỬ (5 NĂM)
* **Trạng thái CRO:** `{cro_eval['verdict']}`
* **Lợi nhuận bình quân năm (CAGR):** `{cro_eval['cagr_pct']:+.2f}%/năm`
* **Mức sụt giảm tối đa (Max Drawdown):** `-{cro_eval['mdd_pct']:.2f}%`
* **Sharpe Ratio:** `{cro_eval['sharpe']:.2f}`
* **Profit Factor:** `{cro_eval['profit_factor']:.2f}`
* **Tỷ lệ thắng (Win Rate):** `{cro_eval['win_rate_pct']:.1f}%`

Chi tiết xem tại: [backtest_report.md](./backtest_report.md)
"""
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write(skill_md_content)
        print(f"📖 Đã tạo tài liệu Skill: {skill_md_path}")

        # 5. Lưu trạng thái status.json
        status_info = {
            "strategy_id": self.strategy_id,
            "title": self.strategy_title,
            "tickers": tickers if isinstance(tickers, list) else [tickers],
            "cro_status": cro_eval["status"],
            "verdict": cro_eval["verdict"],
            "cagr_pct": cro_eval["cagr_pct"],
            "sharpe": cro_eval["sharpe"],
            "mdd_pct": cro_eval["mdd_pct"],
            "html_report": result.get("html_report_path", ""),
            "html_filename": result.get("html_filename", "")
        }
        with open(self.skill_dir / "status.json", "w", encoding="utf-8") as f:
            json.dump(status_info, f, indent=2, ensure_ascii=False)

        print(f"✅ Đóng gói thành công Skill: strategy-{self.strategy_id} (Trạng thái: {cro_eval['status']})")
        return {
            "skill_dir": str(self.skill_dir),
            "cro_eval": cro_eval,
            "metrics": result["metrics"],
            "html_report_path": result.get("html_report_path", "")
        }

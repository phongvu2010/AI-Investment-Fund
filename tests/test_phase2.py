"""
Script Kiểm thử Toàn diện Giai đoạn 2 (Phase 2 Test Suite).
Kiểm tra tính toàn vẹn của:
1. Động cơ vn-backtest (Polars + Numba JIT) tích hợp với dữ liệu Parquet
2. BacktestRunner & PerformanceAnalyzer
3. Report Adapter sinh báo cáo Markdown & Plotly HTML
4. Strategy Generator tự động đóng gói Skill vào .agent/skills/
"""

import sys
from pathlib import Path

# Thêm thư mục gốc vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
import vn_backtest as vb
from backtest.strategy_template import BaseFundStrategy, indicator_sma, indicator_volume_sma
from tools.strategy_generator import StrategySkillPackage

# ====================================================================
# ĐỊNH NGHĨA CHIẾN LƯỢC MẪU: VSA MOMENTUM BREAKOUT
# ====================================================================

class VSAMomentumStrategy(BaseFundStrategy):
    """
    Chiến lược VSA Momentum Breakout:
    - Mua khi Giá vượt lên trên đường MA20 VÀ Khối lượng vượt 1.2 lần trung bình 20 phiên.
    - Bán chốt lời / cắt lỗ khi Giá đóng cửa thủng MA20.
    """

    def init(self):
        # Đăng ký tính toán chỉ báo MA20 giá và MA20 khối lượng
        self.ma20_close = self.I(indicator_sma, length=20, ticker="HPG")
        self.ma20_vol = self.I(indicator_volume_sma, length=20, ticker="HPG")

    def next(self):
        close = self.get_close("HPG")
        vol = self.get_volume("HPG")
        ma20_p = self.ma20_close[-1]
        ma20_v = self.ma20_vol[-1]

        if ma20_p is None or ma20_v is None:
            return

        # Kiểm tra điều kiện Mua: Breakout MA20 + Nổ Vol
        if not self.is_holding("HPG"):
            if close > ma20_p and vol > (1.2 * ma20_v):
                # Mua 5.000 cổ phiếu (lô chẵn)
                self.buy("HPG", size=5000, note="VSA Breakout MA20 + Vol spike")

        # Kiểm tra điều kiện Bán: Thủng MA20
        elif self.is_holding("HPG"):
            if close < ma20_p:
                # Bán toàn bộ vị thế
                qty = self.get_holding_qty("HPG")
                self.sell("HPG", size=qty, note="Thủng MA20 chốt lời/cắt lỗ")


def run_phase2_tests():
    print("=" * 70)
    print("🚀 BẮT ĐẦU KIỂM THỬ GIAI ĐOẠN 2: TÍCH HỢP VN-BACKTEST & ĐÓNG GÓI SKILL")
    print("=" * 70)

    # Khởi tạo gói Skill đóng gói tự động
    package = StrategySkillPackage(
        strategy_id="vsa-momentum",
        strategy_title="VSA Momentum Breakout (HPG)"
    )

    # Chạy quy trình đóng gói & backtest
    result = package.deploy_and_backtest(
        strategy_class=VSAMomentumStrategy,
        tickers="HPG",
        description="Chiến lược theo sau dòng tiền lớn (Smart Money) kết hợp xu hướng MA20 và đột biến Volume.",
        entry_rules="1. Giá đóng cửa vượt lên trên đường MA20.\n2. Khối lượng phiên hiện tại > 1.2 lần khối lượng trung bình 20 phiên.",
        exit_rules="1. Giá đóng cửa giảm thủng xuống dưới đường MA20.\n2. Tuân thủ chu kỳ thanh toán T+2.5 của sàn Việt Nam.",
        days=1250  # 5 năm
    )

    print("\n" + "=" * 70)
    print("📊 KẾT QUẢ THẨM ĐỊNH TỪ GIAI ĐOẠN 2:")
    print("=" * 70)
    metrics = result["metrics"]
    cro_eval = result["cro_eval"]

    print(f"• Trạng thái CRO:     {cro_eval['verdict']}")
    print(f"• Tổng số lệnh:      {metrics.get('total_trades', 0)} lệnh")
    print(f"• Tỷ lệ thắng:       {metrics.get('win_rate', 0)*100:.1f}%")
    print(f"• Lợi nhuận gộp:     {metrics.get('total_return', 0)*100:+.2f}%")
    print(f"• CAGR:              {metrics.get('cagr', 0)*100:+.2f}%/năm")
    print(f"• Max Drawdown:      {abs(metrics.get('max_drawdown', 0))*100:.2f}%")
    print(f"• Sharpe Ratio:      {metrics.get('sharpe_ratio', 0):.2f}")
    print(f"• Profit Factor:     {metrics.get('profit_factor', 0):.2f}")
    print(f"• Thư mục Skill:     {result['skill_dir']}")
    print(f"• Biểu đồ Plotly:    {result['html_report_path']}")

    # Kiểm tra các file đã được tạo đầy đủ
    skill_dir = Path(result["skill_dir"])
    assert (skill_dir / "SKILL.md").exists(), "Thiếu file SKILL.md!"
    assert (skill_dir / "backtest_report.md").exists(), "Thiếu file backtest_report.md!"
    assert (skill_dir / "status.json").exists(), "Thiếu file status.json!"
    assert Path(result["html_report_path"]).exists(), "Thiếu file biểu đồ HTML report!"

    print("\n🎉 GIAI ĐOẠN 2 ĐÃ HOÀN TẤT VÀ KIỂM THỬ THÀNH CÔNG RỰC RỠ!")

if __name__ == "__main__":
    run_phase2_tests()

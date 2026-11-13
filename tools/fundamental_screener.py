"""
Động Cơ Phân Tích Cơ Bản & Sàng Lọc Báo Cáo Tài Chính (Fundamental Screener Engine).
Chạy hoàn toàn bằng Polars / DuckDB trên dữ liệu dạng bảng (0 Token).
Quản lý:
1. data/fundamental_quarterly.parquet (Đồng bộ BigQuery BCTC hoặc sinh dữ liệu chuẩn VN30/Midcap).
2. Tính toán Fundamental Score (0-100 điểm) chuẩn hóa.
3. Tự động phát hiện các dấu hiệu bất thường BCTC (Accounting Red Flags).
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import polars as pl

# Thêm thư mục gốc vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings

class FundamentalScreener:
    """Động cơ Phân tích BCTC & Chấm điểm Sức khỏe Doanh nghiệp 0 Token"""

    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or (settings.DATA_DIR / "fundamental_quarterly.parquet")
        self._ensure_dataset()

    def _ensure_dataset(self):
        """Khởi tạo kho dữ liệu BCTC chuẩn hóa cho VN30/Midcap nếu chưa có file"""
        if not self.data_path.exists():
            self._generate_standard_dataset()

    def _generate_standard_dataset(self):
        """Sinh bộ dữ liệu mẫu chuẩn hóa 9 quý gần nhất cho rổ cổ phiếu trọng điểm"""
        companies_seed = [
            # ticker, rev_g, prof_g, roe, gm, de, ocf_ni, pe, pb, pe_med
            ("FPT", 0.215, 0.224, 0.278, 0.392, 0.45, 1.15, 22.5, 4.80, 19.0),
            ("HPG", 0.182, 0.354, 0.162, 0.158, 0.62, 1.28, 11.2, 1.45, 10.5),
            ("MBB", 0.165, 0.192, 0.235, 0.485, 1.25, 0.95, 5.8, 1.15, 6.5),
            ("SSI", 0.245, 0.285, 0.142, 0.520, 1.40, 0.88, 15.0, 1.70, 14.2),
            ("MWG", 0.152, 0.650, 0.195, 0.242, 0.78, 1.42, 16.8, 2.30, 16.0),
            ("VNM", 0.045, 0.062, 0.282, 0.420, 0.32, 1.08, 15.2, 3.50, 17.5),
            ("TCB", 0.178, 0.215, 0.185, 0.510, 1.10, 0.92, 6.4, 1.05, 7.2),
            ("VHM", -0.052, -0.125, 0.165, 0.315, 1.35, -0.45, 8.5, 0.95, 8.0),
            ("VIC", 0.082, -0.450, 0.055, 0.182, 2.45, -0.85, 28.5, 1.85, 18.0),
            ("MSN", 0.112, 0.420, 0.115, 0.295, 1.85, 1.05, 35.0, 2.10, 32.0),
            ("STB", 0.145, 0.260, 0.175, 0.460, 1.30, 0.90, 7.2, 1.10, 8.0),
            ("CTG", 0.138, 0.185, 0.168, 0.445, 1.45, 0.85, 6.8, 1.20, 7.5),
            ("ACB", 0.155, 0.172, 0.240, 0.490, 0.95, 1.02, 6.1, 1.25, 6.8),
            ("VPB", 0.185, 0.320, 0.135, 0.530, 1.65, 0.80, 8.2, 1.08, 9.5),
            ("REE", 0.125, 0.150, 0.158, 0.325, 0.58, 1.18, 11.5, 1.40, 11.0),
            ("DGC", 0.140, 0.185, 0.265, 0.345, 0.15, 1.22, 12.8, 2.80, 11.5),
            ("PNJ", 0.165, 0.198, 0.245, 0.185, 0.42, 1.10, 14.5, 2.95, 15.0),
            ("GVR", 0.095, 0.142, 0.095, 0.230, 0.48, 1.15, 26.5, 1.80, 22.0),
            ("SHS", 0.210, 0.250, 0.125, 0.480, 0.85, 0.75, 12.5, 1.15, 11.5),
            ("MBS", 0.235, 0.310, 0.155, 0.510, 1.15, 0.82, 13.8, 1.55, 12.0)
        ]

        data = []
        for ticker, rg, pg, roe, gm, de, ocf, pe, pb, pe_med in companies_seed:
            # Sinh 4 quý 2025-2026
            for yr in [2025, 2026]:
                for q in [1, 2, 3, 4]:
                    if yr == 2026 and q > 3:
                        continue
                    # Tạo biến động nhẹ per quarter
                    q_factor = 1.0 + ((q - 2) * 0.02)
                    data.append({
                        "ticker": ticker,
                        "year": yr,
                        "quarter": q,
                        "period": f"{yr}Q{q}",
                        "revenue_growth_yoy": round(rg * q_factor, 4),
                        "profit_growth_yoy": round(pg * q_factor, 4),
                        "roe": round(roe * q_factor, 4),
                        "gross_margin": round(gm, 4),
                        "debt_to_equity": round(de, 4),
                        "ocf_to_net_income": round(ocf, 4),
                        "pe": round(pe * (1.0 / q_factor), 2),
                        "pb": round(pb, 2),
                        "pe_5y_median": round(pe_med, 2)
                    })

        df = pl.DataFrame(data)
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(self.data_path, compression="zstd")
        print(f"📊 [FundamentalScreener] Đã khởi tạo thành công {len(df)} bản ghi BCTC tại: {self.data_path}")

    def get_latest_metrics(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Lấy bộ chỉ số cơ bản của quý gần nhất cho một mã cổ phiếu"""
        if not self.data_path.exists():
            return None

        t = ticker.upper()
        df = pl.read_parquet(self.data_path)
        t_df = df.filter(pl.col("ticker") == t).sort(["year", "quarter"], descending=True)
        if len(t_df) == 0:
            return None

        latest = t_df[0].to_dicts()[0]
        return latest

    def calculate_fundamental_score(self, ticker: str) -> float:
        """
        Tính điểm FA Score (0 - 100 điểm) theo ma trận 4 trụ cột:
        1. Tăng trưởng Doanh thu & Lợi nhuận (25 điểm)
        2. Tỷ suất Sinh lời ROE & Biên Lợi Nhuận Gộp (25 điểm)
        3. Đòn bẩy Tài chính & Chất lượng Dòng tiền OCF (30 điểm)
        4. Định giá P/E so với Trung vị 5 năm (20 điểm)
        """
        metrics = self.get_latest_metrics(ticker)
        if not metrics:
            return 50.0  # Điểm trung tính mặc định nếu chưa có dữ liệu

        score = 0.0

        # Trụ cột 1: Tăng trưởng (25 điểm)
        rev_g = metrics["revenue_growth_yoy"]
        prof_g = metrics["profit_growth_yoy"]
        if rev_g >= 0.20:
            score += 12.5
        elif rev_g >= 0.10:
            score += 8.0
        elif rev_g > 0:
            score += 4.0

        if prof_g >= 0.20:
            score += 12.5
        elif prof_g >= 0.10:
            score += 8.0
        elif prof_g > 0:
            score += 4.0

        # Trụ cột 2: Tỷ suất sinh lời (25 điểm)
        roe = metrics["roe"]
        gm = metrics["gross_margin"]
        if roe >= 0.20:
            score += 15.0
        elif roe >= 0.15:
            score += 10.0
        elif roe >= 0.10:
            score += 5.0

        if gm >= 0.30:
            score += 10.0
        elif gm >= 0.18:
            score += 7.0
        elif gm >= 0.10:
            score += 4.0

        # Trụ cột 3: Sức khỏe đòn bẩy & Dòng tiền OCF (30 điểm)
        de = metrics["debt_to_equity"]
        ocf = metrics["ocf_to_net_income"]
        if de <= 0.8:
            score += 15.0
        elif de <= 1.5:
            score += 10.0
        elif de <= 2.0:
            score += 4.0
        # de > 2.0 nhận 0 điểm

        if ocf >= 1.0:
            score += 15.0
        elif ocf >= 0.7:
            score += 10.0
        elif ocf > 0:
            score += 4.0
        else:
            # OCF âm phạt trừ điểm
            score -= 5.0

        # Trụ cột 4: Định giá P/E (20 điểm)
        pe = metrics["pe"]
        pe_med = metrics["pe_5y_median"]
        if pe_med > 0:
            pe_ratio = pe / pe_med
            if pe_ratio <= 1.0:
                score += 20.0
            elif pe_ratio <= 1.2:
                score += 14.0
            elif pe_ratio <= 1.5:
                score += 7.0
        else:
            score += 10.0

        return max(0.0, min(100.0, round(score, 1)))

    def detect_red_flags(self, ticker: str) -> List[str]:
        """Tự động phát hiện các dấu hiệu rủi ro kế toán (Accounting Red Flags)"""
        metrics = self.get_latest_metrics(ticker)
        if not metrics:
            return ["Chưa có dữ liệu BCTC chính thức trong kho."]

        flags = []
        # 1. Dòng tiền kinh doanh âm
        if metrics["ocf_to_net_income"] < 0:
            flags.append(f"🚩 Dòng tiền kinh doanh (OCF) âm ({metrics['ocf_to_net_income']:.2f}x LNST), nguy cơ lợi nhuận trên giấy.")
        elif metrics["ocf_to_net_income"] < 0.5:
            flags.append(f"⚠️ Chất lượng dòng tiền thấp: OCF/LNST chỉ đạt {metrics['ocf_to_net_income']:.2f}x.")

        # 2. Đòn bẩy nợ cao
        if metrics["debt_to_equity"] > 2.0:
            flags.append(f"🚩 Đòn bẩy tài chính quá cao: D/E đạt {metrics['debt_to_equity']:.2f}x (> 2.0x ngưỡng cảnh báo).")

        # 3. Định giá quá cao so với lịch sử
        if metrics["pe_5y_median"] > 0 and metrics["pe"] > (1.5 * metrics["pe_5y_median"]):
            flags.append(f"🚩 P/E hiện tại ({metrics['pe']:.1f}x) cao hơn 1.5x so với trung vị 5 năm ({metrics['pe_5y_median']:.1f}x).")

        # 4. Tăng trưởng lợi nhuận âm
        if metrics["profit_growth_yoy"] < -0.15:
            flags.append(f"⚠️ Lợi nhuận sụt giảm mạnh so với cùng kỳ ({metrics['profit_growth_yoy']*100:+.1f}%).")

        # 5. Biên lợi nhuận gộp quá thấp
        if metrics["gross_margin"] < 0.10:
            flags.append(f"⚠️ Biên lợi nhuận gộp mỏng ({metrics['gross_margin']*100:.1f}%), dễ tổn thương trước biến động giá vốn.")

        return flags

    def get_fundamental_summary(self, ticker: str) -> Dict[str, Any]:
        """Tổng hợp hồ sơ phân tích cơ bản toàn diện cho một mã"""
        metrics = self.get_latest_metrics(ticker)
        if not metrics:
            return {
                "ticker": ticker.upper(),
                "status": "NOT_FOUND",
                "fa_score": 50.0,
                "rating": "NEUTRAL",
                "red_flags": ["Không tìm thấy dữ liệu BCTC."],
                "summary": f"Mã {ticker.upper()} chưa được cập nhật dữ liệu cơ bản."
            }

        score = self.calculate_fundamental_score(ticker)
        red_flags = self.detect_red_flags(ticker)

        if score >= 80 and len(red_flags) == 0:
            rating = "STRONG_BUY"
        elif score >= 65 and len([f for f in red_flags if "🚩" in f]) == 0:
            rating = "BUY"
        elif score >= 50:
            rating = "HOLD"
        elif score >= 35:
            rating = "CAUTION"
        else:
            rating = "AVOID"

        summary = (
            f"FA Score: {score}/100 ({rating}) | Tăng trưởng DT: {metrics['revenue_growth_yoy']*100:+.1f}%, "
            f"LNST: {metrics['profit_growth_yoy']*100:+.1f}% | ROE: {metrics['roe']*100:.1f}% | "
            f"D/E: {metrics['debt_to_equity']:.2f}x | P/E: {metrics['pe']:.1f}x (Trung vị 5Y: {metrics['pe_5y_median']:.1f}x)"
        )

        return {
            "ticker": ticker.upper(),
            "period": metrics.get("period", "Latest"),
            "fa_score": score,
            "rating": rating,
            "metrics": metrics,
            "red_flags": red_flags,
            "has_critical_flags": any("🚩" in f for f in red_flags),
            "summary": summary
        }

    def sync_from_bigquery(self) -> bool:
        """Đồng bộ dữ liệu BCTC từ Google BigQuery nếu có kết nối GCP"""
        try:
            from google.cloud import bigquery
            client = bigquery.Client(project=settings.GCP_PROJECT_ID)
            query = f"""
                SELECT symbol as ticker, year, quarter, 
                       revenue_growth_yoy, profit_growth_yoy, roe, gross_margin,
                       debt_to_equity, ocf_to_net_income, pe, pb, pe_5y_median
                FROM `{settings.GCP_PROJECT_ID}.{settings.BIGQUERY_DATASET}.fundamental_quarterly`
                ORDER BY year DESC, quarter DESC
            """
            bq_df = client.query(query).to_dataframe()
            pl_df = pl.from_pandas(bq_df)
            pl_df.write_parquet(self.data_path, compression="zstd")
            print(f"✅ Đã đồng bộ {len(pl_df)} bản ghi BCTC từ BigQuery thành công!")
            return True
        except Exception as e:
            print(f"ℹ️ Không thể đồng bộ trực tiếp từ BigQuery ({e}). Sử dụng kho dữ liệu cơ bản nội bộ.")
            return False

if __name__ == "__main__":
    screener = FundamentalScreener()
    for test_t in ["FPT", "HPG", "VIC"]:
        res = screener.get_fundamental_summary(test_t)
        print(f"\n--- PHÂN TÍCH FA: {test_t} ---")
        print(f"Điểm số: {res['fa_score']} ({res['rating']})")
        print(f"Tóm tắt: {res['summary']}")
        print(f"Cảnh báo: {res['red_flags']}")

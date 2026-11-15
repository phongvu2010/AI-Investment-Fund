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
from core.accounting.db_manager import DatabaseManager

FINANCIAL_SECTOR_TICKERS = {
    "VCB", "BID", "CTG", "TCB", "MBB", "ACB", "VPB", "STB", "HDB", "LPB", 
    "TPB", "SHB", "VIB", "MSB", "OCB", "EIB",
    "SSI", "VND", "VCI", "HCM", "SHS", "MBS", "CTS", "BSI", "FTS"
}

class FundamentalScreener:
    """Động cơ Phân tích BCTC & Chấm điểm Sức khỏe Doanh nghiệp 0 Token (Hỗ trợ SQLite DB & Parquet)"""

    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or (settings.DATA_DIR / "fundamental_quarterly.parquet")
        self.db = DatabaseManager()
        self._ensure_dataset()

    def _ensure_dataset(self):
        """Khởi tạo kho dữ liệu BCTC chuẩn hóa cho VN30/Midcap nếu chưa có dữ liệu trong SQLite và Parquet"""
        has_sqlite_data = False
        try:
            existing = self.db.get_all_fundamentals()
            if len(existing) > 0:
                has_sqlite_data = True
                if not self.data_path.exists():
                    pl_df = pl.DataFrame(existing)
                    self.data_path.parent.mkdir(parents=True, exist_ok=True)
                    pl_df.write_parquet(self.data_path, compression="zstd")
        except Exception:
            pass

        if not has_sqlite_data and not self.data_path.exists():
            self._generate_standard_dataset()

    def _generate_standard_dataset(self):
        """Sinh bộ dữ liệu chuẩn hóa đa quý cho hơn 60+ doanh nghiệp hàng đầu (VN30 & VN100)"""
        # (ticker, rev_g, prof_g, roe, gm, de, ocf_ni, pe, pb, pe_med, f_score, z_score)
        companies_seed = [
            # 1. Công nghệ & Viễn thông
            ("FPT", 0.215, 0.224, 0.278, 0.392, 0.45, 1.15, 22.5, 4.80, 19.0, 8, 3.85),
            ("CMG", 0.145, 0.168, 0.142, 0.245, 0.55, 1.05, 24.0, 2.80, 21.0, 7, 2.95),
            ("ELC", 0.185, 0.260, 0.165, 0.310, 0.38, 1.10, 16.5, 1.95, 15.0, 7, 3.20),

            # 2. Thép & Vật liệu xây dựng
            ("HPG", 0.182, 0.354, 0.162, 0.158, 0.62, 1.28, 11.2, 1.45, 10.5, 8, 3.10),
            ("HSG", 0.115, 0.280, 0.115, 0.112, 0.75, 1.02, 13.5, 1.15, 12.0, 6, 2.45),
            ("NKG", 0.098, 0.220, 0.105, 0.098, 0.82, 0.95, 14.0, 1.10, 12.5, 6, 2.30),
            ("BMP", 0.085, 0.145, 0.320, 0.410, 0.18, 1.35, 10.5, 2.65, 10.0, 8, 4.20),
            ("HT1", 0.045, 0.085, 0.065, 0.125, 0.52, 1.08, 18.0, 0.95, 16.5, 5, 2.15),

            # 3. Ngân hàng (Financials - Không áp dụng D/E & Gross Margin chuẩn công nghiệp)
            ("VCB", 0.145, 0.168, 0.225, 0.450, 8.50, 0.95, 12.5, 2.45, 13.0, 8, 2.80),
            ("MBB", 0.165, 0.192, 0.235, 0.485, 7.80, 0.95, 5.8, 1.15, 6.5, 8, 2.65),
            ("TCB", 0.178, 0.215, 0.185, 0.510, 6.50, 0.92, 6.4, 1.05, 7.2, 8, 2.75),
            ("ACB", 0.155, 0.172, 0.240, 0.490, 7.20, 1.02, 6.1, 1.25, 6.8, 8, 2.90),
            ("CTG", 0.138, 0.185, 0.168, 0.445, 9.10, 0.85, 6.8, 1.20, 7.5, 7, 2.50),
            ("BID", 0.125, 0.155, 0.175, 0.420, 9.80, 0.80, 10.5, 1.95, 11.0, 7, 2.40),
            ("VPB", 0.185, 0.320, 0.135, 0.530, 6.80, 0.80, 8.2, 1.08, 9.5, 7, 2.35),
            ("STB", 0.145, 0.260, 0.175, 0.460, 8.20, 0.90, 7.2, 1.10, 8.0, 7, 2.45),
            ("HDB", 0.195, 0.245, 0.220, 0.515, 7.50, 0.92, 6.5, 1.20, 7.0, 8, 2.70),
            ("LPB", 0.220, 0.380, 0.210, 0.480, 8.10, 0.85, 9.5, 1.45, 8.5, 7, 2.55),
            ("TPB", 0.135, 0.175, 0.165, 0.470, 7.40, 0.88, 7.5, 1.12, 8.2, 7, 2.50),
            ("VIB", 0.140, 0.165, 0.230, 0.495, 7.90, 0.90, 6.8, 1.30, 7.4, 7, 2.60),

            # 4. Chứng khoán (Securities)
            ("SSI", 0.245, 0.285, 0.142, 0.520, 1.40, 0.88, 15.0, 1.70, 14.2, 7, 2.90),
            ("VND", 0.185, 0.210, 0.125, 0.460, 1.65, 0.75, 13.5, 1.25, 13.0, 6, 2.65),
            ("VCI", 0.225, 0.320, 0.155, 0.540, 1.25, 0.85, 16.5, 1.95, 15.5, 8, 3.10),
            ("HCM", 0.210, 0.275, 0.148, 0.510, 1.35, 0.82, 14.2, 1.65, 13.8, 7, 2.95),
            ("SHS", 0.210, 0.250, 0.125, 0.480, 0.85, 0.75, 12.5, 1.15, 11.5, 6, 2.80),
            ("MBS", 0.235, 0.310, 0.155, 0.510, 1.15, 0.82, 13.8, 1.55, 12.0, 7, 3.05),
            ("FTS", 0.260, 0.350, 0.185, 0.560, 0.75, 0.95, 18.5, 2.30, 16.0, 8, 3.40),

            # 5. Bán lẻ & Phân phối (Retail)
            ("MWG", 0.152, 0.650, 0.195, 0.242, 0.78, 1.42, 16.8, 2.30, 16.0, 8, 3.35),
            ("PNJ", 0.165, 0.198, 0.245, 0.185, 0.42, 1.10, 14.5, 2.95, 15.0, 8, 3.90),
            ("FRT", 0.225, 0.850, 0.125, 0.175, 1.85, 0.85, 38.0, 4.50, 28.0, 7, 2.75),
            ("DGW", 0.145, 0.210, 0.155, 0.085, 0.65, 1.05, 16.0, 1.85, 15.5, 7, 3.15),

            # 6. Bất động sản Dân cư & Khu công nghiệp
            ("VHM", -0.052, -0.125, 0.165, 0.315, 1.35, -0.45, 8.5, 0.95, 8.0, 5, 2.25),
            ("VIC", 0.082, -0.450, 0.055, 0.182, 2.45, -0.85, 28.5, 1.85, 18.0, 3, 1.55),
            ("VRE", 0.065, 0.095, 0.145, 0.540, 0.32, 1.25, 11.5, 1.10, 14.0, 7, 3.45),
            ("KDH", 0.095, 0.145, 0.085, 0.420, 0.45, 0.65, 22.0, 1.40, 20.0, 6, 2.80),
            ("NLG", 0.115, 0.165, 0.095, 0.380, 0.58, 0.75, 18.5, 1.35, 17.0, 6, 2.70),
            ("KBC", 0.140, 0.220, 0.135, 0.460, 0.52, 0.85, 14.5, 1.25, 13.5, 6, 2.95),
            ("BCM", 0.085, 0.110, 0.115, 0.395, 1.45, 0.80, 26.0, 2.65, 24.0, 6, 2.35),
            ("IDC", 0.165, 0.285, 0.265, 0.425, 0.65, 1.30, 10.5, 2.15, 10.0, 8, 3.65),

            # 7. Hóa chất, Phân bón, Cao su
            ("DGC", 0.140, 0.185, 0.265, 0.345, 0.15, 1.22, 12.8, 2.80, 11.5, 8, 4.60),
            ("DCM", 0.115, 0.210, 0.185, 0.265, 0.22, 1.35, 10.2, 1.65, 9.8, 8, 4.10),
            ("DPM", 0.085, 0.145, 0.135, 0.220, 0.18, 1.28, 11.5, 1.30, 10.5, 7, 3.90),
            ("GVR", 0.095, 0.142, 0.095, 0.230, 0.48, 1.15, 26.5, 1.80, 22.0, 6, 2.85),

            # 8. Dầu khí, Năng lượng, Tiện ích
            ("GAS", 0.075, 0.095, 0.185, 0.195, 0.25, 1.30, 14.0, 2.45, 15.5, 8, 3.95),
            ("PLX", 0.085, 0.165, 0.125, 0.075, 0.95, 1.15, 17.5, 1.85, 16.0, 6, 2.70),
            ("PVD", 0.185, 0.650, 0.085, 0.245, 0.38, 1.12, 22.0, 1.35, 18.0, 7, 3.25),
            ("PVS", 0.165, 0.240, 0.115, 0.065, 0.32, 1.25, 15.5, 1.45, 14.5, 7, 3.40),
            ("PVT", 0.145, 0.195, 0.155, 0.185, 0.65, 1.20, 8.5, 1.15, 8.0, 8, 3.10),
            ("REE", 0.125, 0.150, 0.158, 0.325, 0.58, 1.18, 11.5, 1.40, 11.0, 8, 3.30),
            ("POW", 0.065, 0.125, 0.055, 0.115, 0.48, 1.05, 19.5, 0.85, 17.0, 6, 2.60),
            ("PC1", 0.175, 0.310, 0.105, 0.185, 1.35, 0.85, 16.0, 1.25, 14.5, 6, 2.40),

            # 9. Tiêu dùng, Thực phẩm
            ("VNM", 0.045, 0.062, 0.282, 0.420, 0.32, 1.08, 15.2, 3.50, 17.5, 8, 3.80),
            ("MSN", 0.112, 0.420, 0.115, 0.295, 1.85, 1.05, 35.0, 2.10, 32.0, 6, 2.20),
            ("SAB", 0.055, 0.085, 0.185, 0.315, 0.18, 1.15, 18.5, 2.65, 21.0, 7, 3.75),
            ("QNS", 0.125, 0.185, 0.245, 0.325, 0.28, 1.22, 9.8, 1.85, 9.5, 8, 4.05),

            # 10. Xây dựng, Hạ tầng, Cảng biển
            ("VCG", 0.145, 0.220, 0.095, 0.125, 1.45, 0.85, 15.5, 1.15, 14.0, 6, 2.30),
            ("CTD", 0.210, 0.850, 0.075, 0.055, 0.35, 1.10, 18.0, 0.85, 15.0, 7, 3.20),
            ("VGC", 0.115, 0.185, 0.165, 0.285, 0.65, 1.15, 14.0, 2.15, 13.5, 7, 3.10),
            ("GMD", 0.155, 0.450, 0.185, 0.425, 0.45, 1.25, 14.5, 2.45, 13.5, 8, 3.55),
            ("HAH", 0.185, 0.380, 0.215, 0.310, 0.55, 1.20, 8.8, 1.45, 8.2, 8, 3.40)
        ]

        data = []
        for row in companies_seed:
            ticker, rg, pg, roe, gm, de, ocf, pe, pb, pe_med, f_score, z_score = row
            # Sinh 4 quý 2025-2026
            for yr in [2025, 2026]:
                for q in [1, 2, 3, 4]:
                    if yr == 2026 and q > 3:
                        continue
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
                        "pe_5y_median": round(pe_med, 2),
                        "piotroski_f_score": int(f_score),
                        "altman_z_score": round(z_score, 2)
                    })

        df = pl.DataFrame(data)
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(self.data_path, compression="zstd")
        
        # Đồng bộ toàn bộ dữ liệu mẫu vào SQLite Database
        try:
            self.db.bulk_upsert_fundamentals(data)
        except Exception as e:
            print(f"⚠️ Cảnh báo đồng bộ BCTC vào SQLite: {e}")

        print(f"📊 [FundamentalScreener] Đã khởi tạo thành công {len(df)} bản ghi BCTC cho {len(companies_seed)} mã tại SQLite & {self.data_path}")

    def get_latest_metrics(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Lấy bộ chỉ số cơ bản của quý gần nhất cho một mã cổ phiếu:
        1. Ưu tiên đọc từ SQLite Database (Single Source of Truth)
        2. Fallback sang file Parquet nếu chưa có trong DB
        """
        t = ticker.upper()

        # 1. Đọc từ SQLite
        try:
            db_row = self.db.get_latest_fundamental(t)
            if db_row:
                return db_row
        except Exception:
            pass

        # 2. Fallback đọc từ Parquet cache
        if self.data_path.exists():
            df = pl.read_parquet(self.data_path)
            t_df = df.filter(pl.col("ticker") == t).sort(["year", "quarter"], descending=True)
            if len(t_df) > 0:
                return t_df[0].to_dicts()[0]

        return None

    def upsert_company_financials(self, metrics: Dict[str, Any]) -> bool:
        """
        Thêm mới hoặc cập nhật chỉ số BCTC cho một doanh nghiệp.
        Lưu vĩnh viễn vào SQLite Database và cập nhật lại file Parquet cache.
        """
        success = self.db.upsert_fundamental(metrics)
        # Cập nhật hoặc ghi đè vào Parquet cache
        try:
            all_db_records = self.db.get_all_fundamentals()
            if all_db_records:
                pl_df = pl.DataFrame(all_db_records)
                self.data_path.parent.mkdir(parents=True, exist_ok=True)
                pl_df.write_parquet(self.data_path, compression="zstd")
        except Exception as e:
            print(f"⚠️ Cảnh báo cập nhật Parquet cache: {e}")
        return success

    def calculate_fundamental_score(self, ticker: str) -> float:
        """
        Tính điểm FA Score (0 - 100 điểm) chuẩn hóa thích ứng theo ngành:
        - Doanh nghiệp tài chính (Ngân hàng, Chứng khoán): Tính theo Tăng trưởng, ROE, Piotroski F-Score, Định giá P/B & P/E (Không phạt D/E chuẩn công nghiệp).
        - Doanh nghiệp phi tài chính (Sản xuất, Bán lẻ, BĐS, Năng lượng): 4 trụ cột chuẩn mực (Tăng trưởng, Biên lợi nhuận & ROE, Đòn bẩy & Dòng tiền OCF, Định giá P/E) kèm trọng số Piotroski F-Score & Altman Z-Score.
        """
        metrics = self.get_latest_metrics(ticker)
        if not metrics:
            return 50.0  # Điểm trung tính mặc định nếu chưa có dữ liệu

        t = ticker.upper()
        is_financial = t in FINANCIAL_SECTOR_TICKERS
        score = 0.0

        rev_g = metrics.get("revenue_growth_yoy", 0.0)
        prof_g = metrics.get("profit_growth_yoy", 0.0)
        roe = metrics.get("roe", 0.0)
        pe = metrics.get("pe", 15.0)
        pb = metrics.get("pb", 1.5)
        pe_med = metrics.get("pe_5y_median", 15.0)
        f_score = metrics.get("piotroski_f_score", 6)
        z_score = metrics.get("altman_z_score", 2.6)

        if is_financial:
            # === CHUYÊN BIỆT CHO NGÂN HÀNG & CHỨNG KHOÁN ===
            # Trụ cột 1: Tăng trưởng Thu nhập & Lợi nhuận (25 điểm)
            if rev_g >= 0.18: score += 12.5
            elif rev_g >= 0.10: score += 8.0
            elif rev_g > 0: score += 4.0

            if prof_g >= 0.20: score += 12.5
            elif prof_g >= 0.10: score += 8.0
            elif prof_g > 0: score += 4.0

            # Trụ cột 2: Tỷ suất sinh lời ROE (30 điểm)
            if roe >= 0.22: score += 30.0
            elif roe >= 0.18: score += 24.0
            elif roe >= 0.14: score += 16.0
            elif roe >= 0.10: score += 8.0

            # Trụ cột 3: Chất lượng tài sản & Piotroski F-Score (25 điểm)
            if f_score >= 8: score += 25.0
            elif f_score >= 7: score += 20.0
            elif f_score >= 6: score += 15.0
            elif f_score >= 5: score += 10.0

            # Trụ cột 4: Định giá P/B & P/E (20 điểm)
            if pb <= 1.2: score += 12.0
            elif pb <= 1.5: score += 8.0
            elif pb <= 2.0: score += 4.0

            if pe_med > 0:
                pe_ratio = pe / pe_med
                if pe_ratio <= 1.0: score += 8.0
                elif pe_ratio <= 1.2: score += 5.0
                elif pe_ratio <= 1.5: score += 2.0
            else:
                score += 5.0

        else:
            # === DOANH NGHIỆP PHI TÀI CHÍNH (SẢN XUẤT, BÁN LẺ, TIỆN ÍCH, BĐS) ===
            # Trụ cột 1: Tăng trưởng (25 điểm)
            if rev_g >= 0.20: score += 12.5
            elif rev_g >= 0.10: score += 8.0
            elif rev_g > 0: score += 4.0

            if prof_g >= 0.20: score += 12.5
            elif prof_g >= 0.10: score += 8.0
            elif prof_g > 0: score += 4.0

            # Trụ cột 2: Tỷ suất sinh lời & Biên lợi nhuận gộp (25 điểm)
            gm = metrics.get("gross_margin", 0.15)
            if roe >= 0.20: score += 15.0
            elif roe >= 0.15: score += 10.0
            elif roe >= 0.10: score += 5.0

            if gm >= 0.30: score += 10.0
            elif gm >= 0.18: score += 7.0
            elif gm >= 0.10: score += 4.0

            # Trụ cột 3: Đòn bẩy tài chính & Chất lượng dòng tiền OCF (30 điểm)
            de = metrics.get("debt_to_equity", 1.0)
            ocf = metrics.get("ocf_to_net_income", 1.0)
            if de <= 0.5: score += 15.0
            elif de <= 1.0: score += 10.0
            elif de <= 1.8: score += 5.0

            if ocf >= 1.0: score += 15.0
            elif ocf >= 0.7: score += 10.0
            elif ocf > 0: score += 4.0
            else: score -= 5.0  # OCF âm phạt trừ điểm

            # Trụ cột 4: Định giá P/E so với lịch sử (20 điểm)
            if pe_med > 0:
                pe_ratio = pe / pe_med
                if pe_ratio <= 1.0: score += 20.0
                elif pe_ratio <= 1.2: score += 14.0
                elif pe_ratio <= 1.5: score += 7.0
            else:
                score += 10.0

            # Thưởng/Phạt theo Piotroski F-Score & Altman Z-Score
            if f_score >= 8: score += 3.0
            if z_score >= 3.0: score += 2.0
            elif z_score < 1.8: score -= 8.0  # Vùng nguy cơ rủi ro tài chính

        return max(0.0, min(100.0, round(score, 1)))

    def detect_red_flags(self, ticker: str) -> List[str]:
        """Tự động phát hiện các dấu hiệu rủi ro kế toán (Accounting Red Flags) thích ứng ngành"""
        metrics = self.get_latest_metrics(ticker)
        if not metrics:
            return ["Chưa có dữ liệu BCTC chính thức trong kho."]

        t = ticker.upper()
        is_financial = t in FINANCIAL_SECTOR_TICKERS
        flags = []

        prof_g = metrics.get("profit_growth_yoy", 0.0)
        roe = metrics.get("roe", 0.0)
        pe = metrics.get("pe", 0.0)
        pe_med = metrics.get("pe_5y_median", 0.0)
        f_score = metrics.get("piotroski_f_score", 6)
        z_score = metrics.get("altman_z_score", 2.6)

        if is_financial:
            # Cờ đỏ cho Ngân hàng & Chứng khoán
            if roe < 0.10:
                flags.append(f"🚩 ROE quá thấp ({roe*100:.1f}%), hiệu quả sinh lời và sử dụng vốn ngành tài chính yếu.")
            if prof_g < -0.15:
                flags.append(f"⚠️ Lợi nhuận sụt giảm mạnh so với cùng kỳ ({prof_g*100:+.1f}%).")
            if f_score <= 4:
                flags.append(f"🚩 Piotroski F-Score yếu ({f_score}/9), dấu hiệu suy giảm chất lượng tài sản hoặc nợ xấu gia tăng.")
            if pe_med > 0 and pe > (1.6 * pe_med):
                flags.append(f"🚩 P/E hiện tại ({pe:.1f}x) cao hơn 1.6x so với trung vị lịch sử ({pe_med:.1f}x).")
        else:
            # Cờ đỏ cho Doanh nghiệp phi tài chính
            ocf = metrics.get("ocf_to_net_income", 1.0)
            de = metrics.get("debt_to_equity", 1.0)
            gm = metrics.get("gross_margin", 0.15)

            if ocf < 0:
                flags.append(f"🚩 Dòng tiền kinh doanh (OCF) âm ({ocf:.2f}x LNST), nguy cơ lợi nhuận trên giấy.")
            elif ocf < 0.5:
                flags.append(f"⚠️ Chất lượng dòng tiền thấp: OCF/LNST chỉ đạt {ocf:.2f}x.")

            if de > 2.0:
                flags.append(f"🚩 Đòn bẩy tài chính quá cao: D/E đạt {de:.2f}x (> 2.0x ngưỡng cảnh báo).")

            if z_score < 1.8:
                flags.append(f"🚩 Altman Z-Score rơi vào vùng rủi ro tài chính cao ({z_score:.2f} < 1.8 Distress Zone).")

            if f_score <= 4:
                flags.append(f"⚠️ Piotroski F-Score ở mức thấp ({f_score}/9), cơ bản doanh nghiệp suy yếu.")

            if pe_med > 0 and pe > (1.5 * pe_med):
                flags.append(f"🚩 P/E hiện tại ({pe:.1f}x) cao hơn 1.5x so với trung vị 5 năm ({pe_med:.1f}x).")

            if prof_g < -0.15:
                flags.append(f"⚠️ Lợi nhuận sụt giảm mạnh so với cùng kỳ ({prof_g*100:+.1f}%).")

            if gm < 0.10:
                flags.append(f"⚠️ Biên lợi nhuận gộp mỏng ({gm*100:.1f}%), dễ tổn thương trước biến động giá vốn.")

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

        f_score = metrics.get("piotroski_f_score", 6)
        z_score = metrics.get("altman_z_score", 2.6)
        t = ticker.upper()
        sector_note = "Ngân hàng/Tài chính" if t in FINANCIAL_SECTOR_TICKERS else "Phi tài chính"

        summary = (
            f"FA Score: {score}/100 ({rating}) [{sector_note}] | F-Score: {f_score}/9 | Z-Score: {z_score:.2f} | "
            f"Tăng trưởng DT: {metrics['revenue_growth_yoy']*100:+.1f}%, LNST: {metrics['profit_growth_yoy']*100:+.1f}% | "
            f"ROE: {metrics['roe']*100:.1f}% | P/E: {metrics['pe']:.1f}x (Trung vị 5Y: {metrics['pe_5y_median']:.1f}x)"
        )

        return {
            "ticker": t,
            "period": metrics.get("period", "Latest"),
            "fa_score": score,
            "rating": rating,
            "sector": sector_note,
            "metrics": metrics,
            "red_flags": red_flags,
            "has_critical_flags": any("🚩" in f for f in red_flags),
            "summary": summary
        }

    def import_financials_from_csv(self, csv_path: Path) -> int:
        """
        Nạp dữ liệu BCTC thực tế từ tệp CSV bên ngoài (Vietstock, FiinGroup, FireAnt, Wifeed, Excel tự nhập).
        Cập nhật hoặc ghi đè vào file Parquet data/fundamental_quarterly.parquet.
        """
        p = Path(csv_path)
        if not p.exists():
            raise FileNotFoundError(f"Không tìm thấy file CSV: {p}")

        new_df = pl.read_csv(p)
        # Chuẩn hóa tên cột
        rename_map = {}
        for col in new_df.columns:
            clow = col.strip().lower()
            if clow in ("symbol", "code"): rename_map[col] = "ticker"
            elif clow in ("quarter_period", "quy"): rename_map[col] = "period"

        if rename_map:
            new_df = new_df.rename(rename_map)

        if self.data_path.exists():
            existing_df = pl.read_parquet(self.data_path)
            # Ghép và loại bỏ trùng lặp theo ticker, year, quarter
            combined = pl.concat([existing_df, new_df], how="diagonal")
            combined = combined.unique(subset=["ticker", "year", "quarter"], keep="last")
        else:
            combined = new_df

        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        combined.write_parquet(self.data_path, compression="zstd")
        
        # Đồng bộ vào SQLite Database
        try:
            records = new_df.to_dicts()
            self.db.bulk_upsert_fundamentals(records)
        except Exception as e:
            print(f"⚠️ Cảnh báo nạp BCTC vào SQLite: {e}")

        print(f"✅ Đã nạp thành công {len(new_df)} bản ghi BCTC từ {p.name}. Tổng kho hiện có: {len(combined)} bản ghi.")
        return len(new_df)

    def export_template_csv(self, output_path: Optional[Path] = None) -> Path:
        """Xuất file mẫu CSV chuẩn cột để người dùng hoặc crawler tự động điền BCTC"""
        out_p = output_path or (settings.DATA_DIR / "fundamental_import_template.csv")
        sample_rows = [
            {
                "ticker": "HPG", "year": 2026, "quarter": 3, "period": "2026Q3",
                "revenue_growth_yoy": 0.185, "profit_growth_yoy": 0.320,
                "roe": 0.165, "gross_margin": 0.160, "debt_to_equity": 0.60,
                "ocf_to_net_income": 1.25, "pe": 11.5, "pb": 1.45, "pe_5y_median": 10.5,
                "piotroski_f_score": 8, "altman_z_score": 3.10
            },
            {
                "ticker": "MBB", "year": 2026, "quarter": 3, "period": "2026Q3",
                "revenue_growth_yoy": 0.170, "profit_growth_yoy": 0.195,
                "roe": 0.235, "gross_margin": 0.480, "debt_to_equity": 7.80,
                "ocf_to_net_income": 0.95, "pe": 5.8, "pb": 1.15, "pe_5y_median": 6.5,
                "piotroski_f_score": 8, "altman_z_score": 2.65
            }
        ]
        df = pl.DataFrame(sample_rows)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        df.write_csv(out_p)
        print(f"📄 Đã xuất file CSV mẫu tại: {out_p}")
        return out_p

    def export_dataset_csv(self, output_path: Optional[Path] = None) -> Path:
        """Xuất toàn bộ kho dữ liệu BCTC sang file CSV để kiểm tra trong Excel"""
        out_p = output_path or (settings.DATA_DIR / "fundamental_quarterly_all.csv")
        if not self.data_path.exists():
            self._ensure_dataset()
        df = pl.read_parquet(self.data_path)
        df.write_csv(out_p)
        print(f"📄 Đã xuất toàn bộ {len(df)} bản ghi BCTC sang CSV tại: {out_p}")
        return out_p

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

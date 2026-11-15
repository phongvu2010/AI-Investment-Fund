"""
Động Cơ Tranh Biện Hội Đồng Đầu Tư AI (Adversarial Investment Debate Engine).
Tích hợp:
1. Trí tuệ Nhân tạo Thế hệ mới (Live Gemini GenAI via google.genai SDK) khi có GEMINI_API_KEY.
2. Động cơ Phân tích Phản biện Đa Nhân tố Chuyên sâu (Multi-Factor Quantitative Reasoning)
   hoạt động hoàn toàn tự trị (0 Token) khi chạy offline.
3. Cơ chế Tranh biện Đối kháng:
   - 🐂 Bull Advocate (Phe Bò): Tìm kiếm chất xúc tác tăng trưởng, định giá rẻ, xung lượng dòng tiền.
   - 🐻 Bear Advocate (Red Team - Phe Gấu): Vạch lá tìm sâu, đào bới rủi ro BCTC, bẫy giá giả (Bull-traps),
     áp lực cung đỉnh cũ, rủi ro vĩ mô/khối ngoại.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Thêm thư mục gốc vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings

class InvestmentDebateEngine:
    """Động cơ Tạo Luận Điểm Tranh Biện Đối Kháng cho Hội Đồng Đầu Tư AI"""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"ℹ️ Không thể khởi tạo google.genai Client ({e}). Sẽ sử dụng Multi-Factor Reasoning Engine.")

    def generate_debate(
        self,
        ticker: str,
        strategy_book: str,
        market_regime_info: Dict[str, Any],
        fa_res: Dict[str, Any],
        ml_score: float,
        latest_close: float,
        support_price: float,
        resistance_price: float,
        jev_confidence: Optional[float] = None,
        passes_filter: bool = True
    ) -> Dict[str, Any]:
        """
        Sinh biên bản tranh biện giữa Phe Bò và Phe Gấu.
        Theo kiến trúc Hybrid System 1 + System 2:
        Chỉ kích hoạt LLM (Gemini) khi JevDecisionEngine trả về confidence >= 0.75 và vượt qua bộ lọc sơ bộ.
        Nếu không thỏa mãn, tự động kích hoạt Multi-Factor Reasoning Engine (0 Token).
        """
        t = ticker.upper()
        book = strategy_book.upper()
        price_unit = "k" if latest_close < 1000.0 else "đ"

        # Kiểm tra điều kiện kích hoạt System 2 LLM
        can_trigger_llm = False
        if self.client:
            if jev_confidence is None:
                can_trigger_llm = True
            elif jev_confidence >= 0.75 and passes_filter:
                can_trigger_llm = True
            else:
                print(f"ℹ️ Jev AI System 1 Gate: Confidence {jev_confidence:.2f} < 0.75 hoặc chưa qua sơ lọc. Tiết kiệm Token, dùng Multi-Factor Engine.")

        # Nếu đủ điều kiện, gọi Gemini LLM
        if can_trigger_llm:
            try:
                llm_debate = self._generate_with_gemini(
                    ticker=t,
                    strategy_book=book,
                    market_regime_info=market_regime_info,
                    fa_res=fa_res,
                    ml_score=ml_score,
                    latest_close=latest_close,
                    price_unit=price_unit,
                    support_price=support_price,
                    resistance_price=resistance_price
                )
                if llm_debate:
                    return llm_debate
            except Exception as e:
                print(f"⚠️ Lỗi khi gọi Gemini API ({e}). Tự động chuyển sang Multi-Factor Reasoning Engine.")

        # Fallback: Dynamic Multi-Factor Analytical Debate (0 Token)
        return self._generate_analytical_debate(
            ticker=t,
            strategy_book=book,
            market_regime_info=market_regime_info,
            fa_res=fa_res,
            ml_score=ml_score,
            latest_close=latest_close,
            price_unit=price_unit,
            support_price=support_price,
            resistance_price=resistance_price
        )

    def _generate_with_gemini(
        self,
        ticker: str,
        strategy_book: str,
        market_regime_info: Dict[str, Any],
        fa_res: Dict[str, Any],
        ml_score: float,
        latest_close: float,
        price_unit: str,
        support_price: float,
        resistance_price: float
    ) -> Optional[Dict[str, Any]]:
        """Sinh luận điểm bằng mô hình Gemini thông qua google-genai SDK"""
        from google.genai import types

        regime = market_regime_info.get("regime", "SIDEWAY")
        fa_score = fa_res.get("fa_score", 50.0)
        metrics = fa_res.get("metrics", {})
        red_flags = fa_res.get("red_flags", [])

        prompt = f"""
Bạn là Thư ký Hội đồng Đầu tư của Quỹ Đầu tư AI chuyên nghiệp trên Thị trường Chứng khoán Việt Nam (HOSE/HNX).
Nhiệm vụ: Soạn thảo cuộc tranh biện đối kháng gay gắt giữa 2 nhân sự AI cho mã cổ phiếu [{ticker}] trên Sổ Chiến Lược [{strategy_book}]:

[DỮ LIỆU ĐỊNH LƯỢNG]:
- Thị giá: {latest_close:,.2f} {price_unit} | Hỗ trợ: {support_price:,.2f} | Kháng cự mục tiêu: {resistance_price:,.2f} (+15%)
- Khí tượng thị trường: [{regime}] (Độ rộng: {market_regime_info.get('breadth_ma20_pct', 50)}% > MA20)
- Điểm cơ bản FA Score: {fa_score}/100 ({fa_res.get('rating', 'HOLD')})
- Tăng trưởng DT YoY: {metrics.get('revenue_growth_yoy', 0)*100:+.1f}%, LNST YoY: {metrics.get('profit_growth_yoy', 0)*100:+.1f}%
- ROE: {metrics.get('roe', 0)*100:.1f}%, P/E: {metrics.get('pe', 15):.1f}x (Trung vị 5Y: {metrics.get('pe_5y_median', 15):.1f}x), P/B: {metrics.get('pb', 1.5):.2f}x
- D/E: {metrics.get('debt_to_equity', 0):.2f}x, OCF/LNST: {metrics.get('ocf_to_net_income', 1):.2f}x
- Điểm kỹ thuật ML Alpha Score: {ml_score:.4f}
- Cờ đỏ BCTC phát hiện: {json.dumps(red_flags, ensure_ascii=False)}

YÊU CẦU:
1. Phe Bò (Bull Advocate): 4 luận điểm tăng giá sắc bén, nhấn mạnh chất xúc tác ngành, biên lợi nhuận, định giá và dòng tiền.
2. Phe Gấu (Bear Advocate - Red Team): 3-4 luận điểm phản biện gay gắt, đào sâu rủi ro BCTC, cản kỹ thuật đỉnh cũ, nguy cơ bull-trap, thanh khoản và bối cảnh vĩ mô.
3. Trả về đúng định dạng JSON có 2 key: "bull_arguments" (chuỗi có gạch đầu dòng 1., 2., 3., 4.) và "bear_arguments" (chuỗi có gạch đầu dòng 1., 2., 3., 4.). Không thêm markdown ```json ngoài JSON hợp lệ.
"""
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.4,
                response_mime_type="application/json"
            )
        )

        if response and response.text:
            parsed = json.loads(response.text)
            return {
                "engine": "GEMINI_GENAI",
                "bull_arguments": parsed.get("bull_arguments", ""),
                "bear_arguments": parsed.get("bear_arguments", "")
            }
        return None

    def _generate_analytical_debate(
        self,
        ticker: str,
        strategy_book: str,
        market_regime_info: Dict[str, Any],
        fa_res: Dict[str, Any],
        ml_score: float,
        latest_close: float,
        price_unit: str,
        support_price: float,
        resistance_price: float
    ) -> Dict[str, Any]:
        """Sinh luận điểm bằng động cơ phân tích đa nhân tố tự thích nghi (0 Token)"""
        regime = market_regime_info.get("regime", "SIDEWAY")
        fa_score = fa_res.get("fa_score", 50.0)
        rating = fa_res.get("rating", "HOLD")
        metrics = fa_res.get("metrics", {})
        red_flags = fa_res.get("red_flags", [])

        rev_g = metrics.get("revenue_growth_yoy", 0.0)
        prof_g = metrics.get("profit_growth_yoy", 0.0)
        roe = metrics.get("roe", 0.0)
        pe = metrics.get("pe", 15.0)
        pe_med = metrics.get("pe_5y_median", 15.0)
        pb = metrics.get("pb", 1.5)
        de = metrics.get("debt_to_equity", 0.0)
        ocf = metrics.get("ocf_to_net_income", 1.0)
        f_score = metrics.get("piotroski_f_score", 6)
        z_score = metrics.get("altman_z_score", 2.6)

        # === 1. LUẬN ĐIỂM PHE BÒ (BULL ADVOCATE) ===
        bull_points = []
        if strategy_book == "CORE":
            bull_points.append(
                f"1. Vị thế đầu ngành & Chất lượng BCTC: Điểm FA đạt {fa_score}/100 ({rating}), Piotroski F-Score {f_score}/9 cho thấy sức khỏe tài chính vượt trội."
            )
            if prof_g > 0.15:
                bull_points.append(f"2. Động lực tăng trưởng: Lợi nhuận sau thuế bứt phá +{prof_g*100:.1f}% YoY, doanh thu mở rộng +{rev_g*100:.1f}% khẳng định chu kỳ kinh doanh đang đi lên.")
            else:
                bull_points.append(f"2. Nền tảng sinh lời ổn định: ROE đạt {roe*100:.1f}%, dòng tiền kinh doanh thặng dư vững chắc OCF/LNST = {ocf:.2f}x.")

            if pe_med > 0 and pe < pe_med:
                discount_pct = (1.0 - (pe / pe_med)) * 100
                bull_points.append(f"3. Dư địa định giá hấp dẫn: P/E hiện tại ({pe:.1f}x) đang chiết khấu {discount_pct:.1f}% so với trung vị 5 năm ({pe_med:.1f}x), P/B {pb:.2f}x.")
            else:
                bull_points.append(f"3. Định giá tương xứng vị thế: P/E {pe:.1f}x được hậu thuẫn bởi ROE cao ({roe*100:.1f}%), phù hợp giải ngân tích sản trung dài hạn.")

            bull_points.append(f"4. Kỳ vọng sinh lời mục tiêu: Vùng cản kỹ thuật kỳ vọng tại {resistance_price:,.2f} {price_unit} (+15.0%), điểm tựa hỗ trợ cứng tại {support_price:,.2f} {price_unit}.")

        else: # QUANT BOOK
            bull_points.append(
                f"1. Xung lượng định lượng vượt trội: Mô hình Universal ML Alpha Model chấm {ml_score:.4f} điểm, cho thấy xác suất bứt phá đà tăng trong T+10 rất cao."
            )
            bull_points.append(
                f"2. Dòng tiền xác nhận: Giá nổ volume bứt phá khỏi nền tích lũy MA20, độ rộng thị trường [{regime}] hỗ trợ giải ngân lướt sóng."
            )
            bull_points.append(
                f"3. Tỷ lệ Lợi nhuận / Rủi ro hấp dẫn: Target {resistance_price:,.2f} {price_unit} (+15.0%) so với Stop-loss -7.0% đạt tỷ lệ R:R > 2.1:1."
            )
            bull_points.append(
                f"4. Sức mạnh cơ bản bổ trợ: FA Score {fa_score}/100 đóng vai trò 'tấm đệm an toàn', hạn chế rủi ro bán tháo tháo chạy."
            )

        # === 2. LUẬN ĐIỂM PHE GẤU (BEAR RED-TEAM) ===
        bear_points = []
        if red_flags:
            flags_summary = "; ".join(red_flags[:2])
            bear_points.append(f"1. Rủi ro vi mô / BCTC bất thường: {flags_summary}.")
        elif de > 1.5:
            bear_points.append(f"1. Rủi ro đòn bẩy tài chính: Tỷ lệ Nợ vay D/E ở mức {de:.2f}x, nhạy cảm lớn khi mặt bằng lãi suất biến động.")
        elif ocf < 0.5:
            bear_points.append(f"1. Rủi ro chất lượng dòng tiền: Tỷ lệ OCF/LNST chỉ đạt {ocf:.2f}x, nguy cơ lợi nhuận bị ứ đọng trong các khoản phải thu.")
        else:
            bear_points.append(f"1. Áp lực cung cản kỹ thuật: Vùng đỉnh cũ tại {resistance_price:,.2f} {price_unit} tiềm ẩn lượng hàng kẹp lớn sẵn sàng chốt lời ngắn hạn.")

        if "DOWNTREND" in regime or "RISK_OFF" in regime:
            bear_points.append(f"2. Rủi ro hệ thống từ thị trường chung: Khí tượng [{regime}] với độ rộng suy yếu có thể kéo theo làn sóng bán tháo lan tỏa toàn thị trường.")
        else:
            bear_points.append(f"2. Cạm bẫy giá giả (Bull-trap): Cần cảnh giác phiên nổ volume giả do kéo trụ chỉ số trong khi thanh khoản chung chưa lan tỏa đồng đều.")

        if pe_med > 0 and pe > pe_med * 1.2:
            bear_points.append(f"3. Bất lợi về định giá: P/E hiện tại ({pe:.1f}x) cao hơn 20% so với trung vị lịch sử ({pe_med:.1f}x), dư địa tăng trưởng đã phản ánh phần lớn vào giá.")
        else:
            bear_points.append(f"3. Rủi ro biến động khối ngoại: Khối ngoại có thể tiếp tục bán ròng cơ cấu danh mục, kiềm hãm đà bứt phá của cổ phiếu.")

        bull_text = "\n".join(bull_points)
        bear_text = "\n".join(bear_points)

        return {
            "engine": "MULTI_FACTOR_REASONING_0_TOKEN",
            "bull_arguments": bull_text,
            "bear_arguments": bear_text
        }

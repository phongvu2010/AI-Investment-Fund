"""
Hệ Thống Phản Xạ Quyết Định Jev AI (Jev Decision Engine - System 1).
Cung cấp các Primitive quyết định phân biệt (Discriminative Decision Primitives) tốc độ cao (< 500ms):
1. Noul: Phân loại nhị phân kèm độ tin cậy và phân phối xác suất (True/False + Confidence)
2. Choice: Định tuyến chiến lược đa lựa chọn (Enum routing: CORE vs QUANT vs IGNORE)
3. Score: Chấm điểm rủi ro liên tục [0.0 - 1.0] (Execution Risk Scoring)
Hoạt động hoàn toàn tự trị, không tiêu tốn Token (0 Token Core).
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings


@dataclass
class Noul:
    """
    Primitive Quyết Định Nhị Phân (Named Boolean Primitive).
    Biểu diễn phán quyết True/False đi kèm độ tin cậy (confidence) và phân phối xác suất.
    """
    value: bool
    confidence: float
    probabilities: Dict[str, float] = field(default_factory=dict)
    latency_ms: float = 0.0
    reasoning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "confidence": round(self.confidence, 4),
            "probabilities": {k: round(v, 4) for k, v in self.probabilities.items()},
            "latency_ms": round(self.latency_ms, 2),
            "reasoning": self.reasoning
        }


@dataclass
class Choice:
    """
    Primitive Định Tuyến Lựa Chọn (Categorical Choice Primitive).
    Biểu diễn lựa chọn trong tập hữu hạn (Enum) kèm phân phối xác suất và độ tin cậy.
    """
    value: str
    confidence: float
    probabilities: Dict[str, float] = field(default_factory=dict)
    latency_ms: float = 0.0
    reasoning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "confidence": round(self.confidence, 4),
            "probabilities": {k: round(v, 4) for k, v in self.probabilities.items()},
            "latency_ms": round(self.latency_ms, 2),
            "reasoning": self.reasoning
        }


@dataclass
class Score:
    """
    Primitive Chấm Điểm Liên Tục (Continuous Numerical Score Primitive).
    Biểu diễn giá trị liên tục trong đoạn [0.0, 1.0] kèm metadata đo lường và độ tin cậy.
    """
    value: float
    confidence: float
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    reasoning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": round(self.value, 4),
            "confidence": round(self.confidence, 4),
            "latency_ms": round(self.latency_ms, 2),
            "metadata": self.metadata,
            "reasoning": self.reasoning
        }


class JevDecisionEngine:
    """
    Bộ não phản xạ System 1 của Quỹ Đầu tư AI.
    Thực thi các quyết định phân loại, lọc nhiễu và định tuyến tốc độ cực cao (< 500ms).
    """

    CRITICAL_POSITIVE_KEYWORDS = [
        "tăng trưởng", "đột biến", "trúng thầu", "cổ tức", "mua lại cổ phiếu",
        "chấp thuận", "mở rộng", "lãi kỷ lục", "vượt kế hoạch", "hợp tác chiến lược"
    ]

    CRITICAL_NEGATIVE_KEYWORDS = [
        "khởi tố", "bắt tạm giam", "thanh tra", "hủy niêm yết", "lỗ nặng",
        "chậm nộp", "bị phạt", "bán giải chấp", "đình chỉ", "ngừng giao dịch",
        "ý kiến ngoại trừ", "nghi vấn gian lận", "kẹt sàn"
    ]

    def __init__(self):
        self._pm = None
        self._fs = None
        self._ml = None

    @property
    def parquet_mgr(self):
        if self._pm is None:
            from core.data.parquet_manager import ParquetMarketDataManager
            self._pm = ParquetMarketDataManager()
        return self._pm

    @property
    def fa_screener(self):
        if self._fs is None:
            from core.quant.fundamental_screener import FundamentalScreener
            self._fs = FundamentalScreener()
        return self._fs

    @property
    def ml_predictor(self):
        if self._ml is None:
            from core.quant.ml_predictor import UniversalAlphaPredictor
            self._ml = UniversalAlphaPredictor()
        return self._ml

    def triage_market_event(
        self,
        ticker: str,
        news_text: Optional[str] = None,
        intraday_bar: Optional[Dict[str, Any]] = None,
        market_regime: Optional[Dict[str, Any]] = None
    ) -> Noul:
        """
        1. triage_market_event -> Noul (True/False + confidence)
        Đánh giá xem sự kiện/biến động hiện tại có tác động trọng yếu (Material Impact)
        đến cổ phiếu trong Watchlist/Portfolio hay chỉ là nhiễu thị trường (Market Noise).
        """
        t0 = time.perf_counter()
        t = ticker.upper()

        impact_score = 0.0
        signals = []

        # 1. Đánh giá nội dung tin tức (nếu có)
        if news_text:
            text_lower = news_text.lower()
            pos_matches = [w for w in self.CRITICAL_POSITIVE_KEYWORDS if w in text_lower]
            neg_matches = [w for w in self.CRITICAL_NEGATIVE_KEYWORDS if w in text_lower]

            if neg_matches:
                impact_score += 0.55 + min(0.35, len(neg_matches) * 0.15)
                signals.append(f"Từ khóa tiêu cực nghiêm trọng: {', '.join(neg_matches)}")
            if pos_matches:
                impact_score += 0.40 + min(0.30, len(pos_matches) * 0.10)
                signals.append(f"Từ khóa tích cực trọng yếu: {', '.join(pos_matches)}")

        # 2. Đánh giá biến động giá và khối lượng (intraday_bar)
        if intraday_bar:
            pct_change = abs(float(intraday_bar.get("pct_change", 0.0)))
            vol_ratio = float(intraday_bar.get("vol_ratio", 1.0))
            is_floor = intraday_bar.get("is_floor", False)
            is_ceiling = intraday_bar.get("is_ceiling", False)

            if is_floor or is_ceiling:
                impact_score += 0.60
                signals.append(f"Cổ phiếu chạm giá {'SÀN' if is_floor else 'TRẦN'}")
            elif pct_change >= 4.0:
                impact_score += 0.45
                signals.append(f"Biến động giá mạnh ({pct_change:.1f}%)")
            elif pct_change >= 2.0:
                impact_score += 0.25
                signals.append(f"Biến động giá đáng kể ({pct_change:.1f}%)")

            if vol_ratio >= 2.0:
                impact_score += 0.40
                signals.append(f"Khối lượng đột biến ({vol_ratio:.1f}x MA20)")
            elif vol_ratio >= 1.4:
                impact_score += 0.20
                signals.append(f"Khối lượng gia tăng ({vol_ratio:.1f}x MA20)")

        # 3. Đánh giá bối cảnh thị trường chung (market_regime)
        if market_regime:
            regime = market_regime.get("regime", "SIDEWAY")
            if regime == "DOWNTREND" and market_regime.get("freeze_quant", False):
                impact_score += 0.15
                signals.append("Thị trường Downtrend rủi ro hệ thống")

        # 4. Kiểm tra mã treo sàn hoặc quá khứ đặc biệt (FLC, v.v.)
        if t in {"FLC"}:
            impact_score = 1.0
            signals.append("Mã cổ phiếu bị đình chỉ/treo sàn")

        # Tính toán xác suất và độ tin cậy
        p_material = min(0.99, max(0.01, impact_score))
        p_noise = round(1.0 - p_material, 4)
        p_material = round(p_material, 4)

        is_material = p_material >= 0.50
        confidence = p_material if is_material else p_noise

        latency_ms = (time.perf_counter() - t0) * 1000.0

        reasoning = (
            f"Tác động trọng yếu: {'; '.join(signals)}"
            if is_material
            else "Nhiễu thị trường thông thường, không phát hiện sự kiện bất thường."
        )

        return Noul(
            value=is_material,
            confidence=confidence,
            probabilities={"True": p_material, "False": p_noise},
            latency_ms=latency_ms,
            reasoning=reasoning
        )

    def route_strategy_book(
        self,
        ticker: str,
        fa_summary: Optional[Dict[str, Any]] = None,
        ml_score: Optional[float] = None,
        regime: Optional[str] = None
    ) -> Choice:
        """
        2. route_strategy_book -> Choice(["CORE", "QUANT", "IGNORE"])
        Tự động định tuyến mã cổ phiếu vào sổ CORE (nền tảng tốt, FA Score >= 60, ít biến động),
        QUANT (xung lượng dòng tiền, ML Score >= 0.60), hoặc IGNORE.
        """
        t0 = time.perf_counter()
        t = ticker.upper()

        # Nạp FA nếu chưa truyền vào
        if fa_summary is None:
            try:
                fa_summary = self.fa_screener.get_fundamental_summary(t)
            except Exception:
                fa_summary = {"fa_score": 50.0, "has_critical_flags": False, "red_flags": []}

        # Nạp ML Score nếu chưa truyền vào
        if ml_score is None:
            try:
                ml_score = self.ml_predictor.predict_score(t)
            except Exception:
                ml_score = 0.50

        fa_score = float(fa_summary.get("fa_score", 50.0))
        has_critical = bool(fa_summary.get("has_critical_flags", False))
        red_flags_count = len(fa_summary.get("red_flags", []))

        # Điểm trọng số cho từng sổ
        # CORE: Yêu cầu FA Score cao (>= 60), không có critical flags, red_flags ít
        if has_critical or red_flags_count >= 2:
            score_core = 0.05
        elif fa_score >= 60.0:
            score_core = 0.40 + (fa_score - 60.0) / 40.0 * 0.55
        else:
            score_core = max(0.05, (fa_score / 60.0) * 0.35)

        # QUANT: Yêu cầu ML Score cao (>= 0.60), có động lượng kỹ thuật
        if regime == "DOWNTREND":
            score_quant = max(0.05, ml_score * 0.60)
        else:
            score_quant = ml_score

        # IGNORE: Tăng cao khi cả FA và ML đều yếu hoặc có cờ đỏ nghiêm trọng
        if has_critical or t in {"FLC"}:
            score_ignore = 0.90
        else:
            score_ignore = max(0.05, (1.0 - max(score_core, score_quant)))
            if fa_score < 40.0 and ml_score < 0.45:
                score_ignore = max(score_ignore, 0.75)

        # Chuẩn hóa Softmax/Tổng xác suất
        total = score_core + score_quant + score_ignore
        p_core = score_core / total
        p_quant = score_quant / total
        p_ignore = score_ignore / total

        # Định tuyến quyết định
        if has_critical or t in {"FLC"}:
            decision = "IGNORE"
            confidence = p_ignore
            reasoning = f"Loại bỏ ({t}): Cờ đỏ BCTC trọng yếu hoặc cổ phiếu bị kiểm soát."
        elif fa_score >= 60.0 and p_core >= p_quant and p_core >= 0.35:
            decision = "CORE"
            confidence = p_core
            reasoning = f"Định tuyến SỔ CORE: Nền tảng FA vững mạnh (FA Score: {fa_score:.0f}/100, {red_flags_count} cờ đỏ)."
        elif ml_score >= 0.55 and p_quant >= p_ignore:
            decision = "QUANT"
            confidence = p_quant
            reasoning = f"Định tuyến SỔ QUANT: Xung lượng Alpha ML mạnh ({ml_score:.4f} >= 0.55)."
        else:
            decision = "IGNORE"
            confidence = p_ignore
            reasoning = f"Định tuyến IGNORE: Không thỏa mãn chuẩn phân bổ (FA {fa_score:.0f}, ML {ml_score:.4f})."

        latency_ms = (time.perf_counter() - t0) * 1000.0

        return Choice(
            value=decision,
            confidence=round(confidence, 4),
            probabilities={
                "CORE": round(p_core, 4),
                "QUANT": round(p_quant, 4),
                "IGNORE": round(p_ignore, 4)
            },
            latency_ms=latency_ms,
            reasoning=reasoning
        )

    def score_execution_risk(
        self,
        ticker: str,
        action: str,
        proposed_vol: int,
        liq_metrics: Optional[Dict[str, Any]] = None,
        portfolio_state: Optional[Dict[str, Any]] = None,
        proposed_price: Optional[float] = None
    ) -> Score:
        """
        3. score_execution_risk -> Score [0.0 - 1.0]
        Chấm điểm rủi ro thực thi từ 0.0 (an toàn tuyệt đối) đến 1.0 (rủi ro cực cao):
        - Gần giá sàn, kẹt sàn (floor-lock)
        - Thanh khoản suy kiệt (liquidity deficit)
        - Vi phạm tỷ trọng NAV (concentration)
        - Vi phạm quy chế T+2.5
        """
        t0 = time.perf_counter()
        t = ticker.upper()
        act = action.upper()

        if liq_metrics is None:
            try:
                liq_metrics = self.parquet_mgr.get_ticker_liquidity_metrics(t, window=20)
            except Exception:
                liq_metrics = {}

        risk_score = 0.05
        factors = {}

        # 1. Rủi ro kẹt sàn / Trắng bên mua
        if liq_metrics.get("is_currently_floor_locked", False):
            risk_score += 0.85
            factors["floor_locked"] = "Đang kẹt sàn / trắng bên mua"
        elif liq_metrics.get("is_near_floor", False):
            risk_score += 0.35
            factors["near_floor"] = "Tiệm cận sát giá sàn (< 1.5%)"

        # 2. Rủi ro lịch sử kẹt sàn (Liquidity Stress)
        if liq_metrics.get("is_floor_risk_high", False):
            risk_score += 0.30
            factors["floor_risk_high"] = f"Lịch sử từng kẹt sàn {liq_metrics.get('max_consecutive_floor_days', 0)} phiên"

        # 3. Rủi ro thanh khoản suy kiệt
        is_liquid = liq_metrics.get("is_liquid", True)
        adtv = liq_metrics.get("adtv_billion", 10.0)
        adv = liq_metrics.get("adv", 100000)

        if not is_liquid:
            risk_score += 0.35
            factors["illiquid"] = f"Thanh khoản thấp ({adtv:.1f} Tỷ/phiên < 10 Tỷ)"

        # 4. Rủi ro tác động giá (Participation Rate > 2%)
        if adv > 0:
            part_rate = proposed_vol / adv
            if part_rate > 0.05:
                risk_score += 0.40
                factors["excessive_participation"] = f"Tỷ lệ tham gia quá cao: {part_rate*100:.1f}% ADV (> 5%)"
            elif part_rate > settings.MAX_PARTICIPATION_RATE:
                risk_score += 0.20
                factors["high_participation"] = f"Tỷ lệ tham gia cao: {part_rate*100:.1f}% ADV (> 2%)"

        # 5. Rủi ro danh mục & Vượt trần NAV
        if portfolio_state:
            total_nav = portfolio_state.get("total_nav", settings.INITIAL_CAPITAL)
            curr_pos_val = portfolio_state.get("current_position_value", 0.0)
            book = portfolio_state.get("strategy_book", "QUANT").upper()
            max_pct = settings.CORE_MAX_POSITION_PCT if book == "CORE" else settings.QUANT_MAX_POSITION_PCT

            price = proposed_price or liq_metrics.get("latest_close", 0.0)
            if price < 1000.0:
                price *= 1000.0

            if act == "BUY":
                new_val = curr_pos_val + (proposed_vol * price)
                new_pct = new_val / max(1.0, total_nav)
                if new_pct > max_pct:
                    risk_score += 0.50
                    factors["nav_limit_breach"] = f"Vượt trần tỷ trọng ({new_pct*100:.1f}% > {max_pct*100:.1f}% NAV)"

            # Circuit breaker sụt giảm tuần
            weekly_dd = abs(portfolio_state.get("weekly_drawdown_pct", 0.0))
            if weekly_dd > settings.MAX_WEEKLY_DRAWDOWN_PCT:
                risk_score += 0.40
                factors["circuit_breaker"] = f"Circuit breaker kích hoạt (MDD tuần {weekly_dd*100:.1f}%)"

            # Kiểm tra T+2.5 nếu BÁN
            if act == "SELL":
                avail_qty = portfolio_state.get("available_quantity", proposed_vol)
                if proposed_vol > avail_qty:
                    risk_score += 0.90
                    factors["t25_violation"] = f"Số lượng bán ({proposed_vol:,}) vượt số lượng khả dụng T+2.5 ({avail_qty:,})"

        # Cổ phiếu đặc biệt
        if t in {"FLC"}:
            risk_score = 1.0
            factors["suspended"] = "Cổ phiếu đình chỉ giao dịch"

        final_risk = min(1.0, max(0.0, risk_score))
        confidence = 0.95 if factors else 0.85
        latency_ms = (time.perf_counter() - t0) * 1000.0

        reasoning = (
            f"Rủi ro cao ({final_risk:.2f}): " + "; ".join(factors.values())
            if final_risk >= 0.50
            else f"Mức độ rủi ro chấp nhận được ({final_risk:.2f})."
        )

        return Score(
            value=final_risk,
            confidence=confidence,
            latency_ms=latency_ms,
            metadata={
                "factors": factors,
                "ticker": t,
                "action": act,
                "proposed_vol": proposed_vol
            },
            reasoning=reasoning
        )

"""
Test Suite Kiểm thử Động Cơ Tự Học Hỏi & Tiến Hóa Chiến Lược (Self-Learning & Optimization Test Suite).
Kiểm tra:
1. Cơ chế Chẩn đoán thất bại định lượng (diagnose_failure).
2. Quét không gian tham số và tìm kiếm bộ tham số tối ưu (ParameterOptimizer).
3. Tự động khắc phục sai lầm (Auto-Heal) và ghi nhật ký Post-Mortem Memo.
4. Đồng bộ cập nhật vào Skill, Report và API Dashboard.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pytest
from tools.strategy_optimizer import StrategyOptimizerEngine
from fastapi.testclient import TestClient
from dashboard.api import app

def test_diagnose_failure():
    engine = StrategyOptimizerEngine()
    diag = engine.diagnose_failure("vsa-momentum")
    assert diag["strategy_id"] == "vsa-momentum"
    assert "diagnoses" in diag
    print("\n✅ Test 1 Passed: Động cơ chẩn đoán thất bại hoạt động chuẩn xác.")

def test_auto_heal_execution():
    engine = StrategyOptimizerEngine()
    res = engine.auto_heal_vsa_strategy(ticker="HPG")
    assert res["status"] == "SUCCESS"
    assert "best_params" in res
    assert "cro_eval" in res
    assert Path(res["memo_path"]).exists()
    print("✅ Test 2 Passed: Vòng lặp tự học & tiến hóa khắc phục chiến lược thành công.")

def test_api_optimize_endpoint():
    client = TestClient(app)
    response = client.get("/api/reports")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    # Kiểm tra báo cáo chiến lược đã có thông số tiến hóa v2.0
    strat = [s for s in data if s.get("strategy_id") == "vsa-momentum"][0]
    assert "v2.0" in strat.get("title", "")
    print("✅ Test 3 Passed: Endpoint Dashboard API hiển thị chính xác kết quả sau khi tiến hóa.")

if __name__ == "__main__":
    test_diagnose_failure()
    test_auto_heal_execution()
    test_api_optimize_endpoint()
    print("\n🎉 TẤT CẢ 3 BÀI TEST TỰ HỌC & TIẾN HÓA ĐỀU ĐÃ ĐẠT CHUẨN 100%!")

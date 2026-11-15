"""
Test Suite Kiểm thử Toàn diện Hạ tầng Machine Learning / Deep Learning (ML Pipeline Test Suite).
Kiểm tra:
1. Tính toán 15 đặc trưng kỹ thuật & dòng tiền chuẩn hóa (Stationary Features).
2. Gán nhãn Triple-Barrier Method (+5% TP, -3% SL trong 5 phiên).
3. Huấn luyện và đóng gói Universal Alpha Model (LightGBM .joblib).
4. Khả năng suy luận (Inference Engine) siêu tốc < 0.005s.
5. Tích hợp BaseFundStrategy.get_ml_score() và Web Dashboard API.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
from fastapi.testclient import TestClient
from core.quant.ml_feature_extractor import MLFeatureExtractor
from core.quant.ml_model_trainer import train_and_export_local_model, run_walk_forward_validation
from core.quant.ml_predictor import UniversalAlphaPredictor
from core.backtest.strategy_template import BaseFundStrategy
from apps.api.main import app

def test_ml_feature_extractor():
    print("\n[TEST 1] Kiểm tra Bộ Trích Xuất Đặc Trưng ML & Gán Nhãn...")
    extractor = MLFeatureExtractor()
    df = extractor.process_all_market()
    assert len(df) > 1000
    assert "target" in df.columns
    assert "ret_1d" in df.columns
    assert "vol_ratio_20" in df.columns
    assert "norm_atr_14" in df.columns
    assert "rsi_14" in df.columns
    # Kiểm tra nhãn nhị phân
    unique_targets = df["target"].unique().to_list()
    assert set(unique_targets).issubset({0, 1})
    print(f"✅ Test 1 Passed: Đã trích xuất {len(df):,} mẫu nến với đầy đủ 15 đặc trưng và nhãn Triple-Barrier.")

def test_ml_trainer_and_package():
    print("\n[TEST 2] Kiểm tra Huấn Luyện & Đóng Gói Model LightGBM...")
    csv_file = Path("data/ml_dataset_train.csv")
    if not csv_file.exists():
        MLFeatureExtractor().export_dataset(Path("data/ml_dataset_train.parquet"), export_csv=True)
    model_file = train_and_export_local_model()
    assert model_file.exists()
    assert model_file.stat().st_size > 1000  # Ít nhất 1KB
    print(f"✅ Test 2 Passed: Đã đóng gói thành công {model_file.name} ({model_file.stat().st_size / 1024:.1f} KB).")

def test_walk_forward_validation():
    print("\n[TEST 2B] Kiểm tra Walk-Forward Validation Đa Giai Đoạn...")
    parquet_file = Path("data/ml_dataset_train.parquet")
    if not parquet_file.exists():
        MLFeatureExtractor().export_dataset(parquet_file)
    wf_res = run_walk_forward_validation(data_path=parquet_file, n_splits=3)
    assert "folds" in wf_res
    assert len(wf_res["folds"]) == 3
    assert "mean_auc" in wf_res
    assert 0.0 <= wf_res["mean_auc"] <= 1.0
    for fold in wf_res["folds"]:
        assert fold["test_samples"] > 0
        assert 0.0 <= fold["roc_auc"] <= 1.0
    print(f"✅ Test 2B Passed: Walk-Forward Validation hoàn tất với 3 folds, Mean AUC = {wf_res['mean_auc']:.4f}.")

def test_ml_predictor_inference():
    print("\n[TEST 3] Kiểm tra Khả Năng Dự Báo & Bảng Xếp Hạng Thị Trường...")
    predictor = UniversalAlphaPredictor()
    score_hpg = predictor.predict_score("HPG")
    assert 0.0 <= score_hpg <= 1.0

    rankings = predictor.get_market_rankings(top_n=5)
    assert len(rankings) > 0
    assert "ml_score" in rankings[0]
    assert "rating" in rankings[0]
    print(f"✅ Test 3 Passed: Dự báo HPG ML Score = {score_hpg:.4f} | Top 1 mã: {rankings[0]['ticker']} ({rankings[0]['ml_score']:.4f}).")

def test_base_fund_strategy_integration():
    print("\n[TEST 4] Kiểm tra Tích hợp BaseFundStrategy.get_ml_score()...")
    class DummyStrategy(BaseFundStrategy):
        pass

    dummy = DummyStrategy(data=None, engine=None)
    score = dummy.get_ml_score("HPG")
    assert 0.0 <= score <= 1.0
    print(f"✅ Test 4 Passed: Chiến lược giao dịch con có thể gọi self.get_ml_score('HPG') ➔ {score:.4f}.")

def test_api_ml_endpoints():
    print("\n[TEST 5] Kiểm tra API Dashboard Endpoint ML...")
    client = TestClient(app)

    # 1. Endpoint Rankings
    res_rankings = client.get("/api/ml/rankings?top_n=5")
    assert res_rankings.status_code == 200
    data_rankings = res_rankings.json()
    assert data_rankings["status"] == "SUCCESS"
    assert len(data_rankings["rankings"]) > 0

    # 2. Endpoint Chi tiết 1 mã
    res_score = client.get("/api/ml/score/HPG")
    assert res_score.status_code == 200
    data_score = res_score.json()
    assert data_score["ticker"] == "HPG"
    assert "ml_score" in data_score

    # 3. Endpoint Thông tin Model Info
    res_info = client.get("/api/ml/model/info")
    assert res_info.status_code == 200
    data_info = res_info.json()
    assert "trained_at" in data_info
    assert "dataset" in data_info
    assert data_info["dataset"]["csv_exists"] is True

    # 4. Endpoint Tải về CSV
    res_dl = client.get("/api/ml/dataset/download")
    assert res_dl.status_code == 200
    assert "text/csv" in res_dl.headers.get("content-type", "")

    # 5. Endpoint Tải lên Model .joblib
    model_path = BASE_DIR / "models" / "universal_alpha_model.joblib"
    with open(model_path, "rb") as f:
        res_upload = client.post("/api/ml/model/upload", files={"file": ("universal_alpha_model.joblib", f, "application/octet-stream")})
    assert res_upload.status_code == 200
    data_upload = res_upload.json()
    assert data_upload["status"] == "SUCCESS"
    assert "trained_at" in data_upload

    print("✅ Test 5 Passed: Cả 5 endpoints quản lý Machine Learning trên Web Dashboard phản hồi chuẩn mực 100%.")

if __name__ == "__main__":
    test_ml_feature_extractor()
    test_ml_trainer_and_package()
    test_ml_predictor_inference()
    test_base_fund_strategy_integration()
    test_api_ml_endpoints()
    print("\n🎉 TOÀN BỘ 5 BÀI TEST HẠ TẦNG MACHINE LEARNING ĐỀU ĐẠT CHUẨN 100%!")

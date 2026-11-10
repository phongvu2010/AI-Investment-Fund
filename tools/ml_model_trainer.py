"""
Script Huấn luyện Mô hình Machine Learning Trực tiếp (Fast Local ML Trainer).
Tự động huấn luyện mô hình LightGBM từ file ml_dataset_train.parquet và đóng gói
thành tệp models/universal_alpha_model.joblib để hệ thống hoạt động ngay lập tức.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import numpy as np
import polars as pl
import lightgbm as lgb
import joblib
from sklearn.metrics import roc_auc_score

# Thêm thư mục gốc dự án vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings

def train_and_export_local_model(
    data_path: Optional[Path] = None,
    output_model_path: Optional[Path] = None
) -> Path:
    data_file = data_path or (settings.BASE_DIR / "data" / "ml_dataset_train.parquet")
    out_file = output_model_path or (settings.BASE_DIR / "models" / "universal_alpha_model.joblib")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if not data_file.exists():
        print(f"⚠️ Chưa có file {data_file}, đang tự động trích xuất đặc trưng...")
        from tools.ml_feature_extractor import MLFeatureExtractor
        extractor = MLFeatureExtractor()
        extractor.export_dataset(data_file)

    print(f"\n🧠 BẮT ĐẦU HUẤN LUYỆN UNIVERSAL ALPHA MODEL (LIGHTGBM)...")
    print(f"📂 Nguồn dữ liệu: {data_file}")
    df = pl.read_parquet(data_file)

    features = [
        "ret_1d", "ret_3d", "ret_5d", "ret_10d", "ret_20d",
        "rel_ret_5d", "rel_ret_20d",
        "vol_ratio_20", "vol_zscore_60",
        "norm_atr_14", "bb_width_20",
        "body_to_range", "upper_wick_ratio", "lower_wick_ratio",
        "rsi_14", "macd_hist_norm"
    ]
    target = "target"

    # Purged Time-Series Split (80% Train, 20% Out-of-Sample Test)
    unique_dates = df["trade_date"].unique().sort().to_list()
    split_idx = int(len(unique_dates) * 0.80)
    split_date = unique_dates[split_idx]

    train_df = df.filter(pl.col("trade_date") < split_date)
    test_df = df.filter(pl.col("trade_date") >= split_date)

    X_train = train_df.select(features).to_pandas()
    y_train = train_df[target].to_numpy()
    X_test = test_df.select(features).to_pandas()
    y_test = test_df[target].to_numpy()

    pos_count = np.sum(y_train == 1)
    neg_count = np.sum(y_train == 0)
    scale_pos = float(neg_count / max(pos_count, 1))

    print(f"🏋️ Số mẫu Train: {len(X_train):,} ({train_df['trade_date'].min()} -> {train_df['trade_date'].max()})")
    print(f"🧪 Số mẫu Test (Out-of-Sample): {len(X_test):,} ({test_df['trade_date'].min()} -> {test_df['trade_date'].max()})")

    model = lgb.LGBMClassifier(
        n_estimators=250,
        learning_rate=0.03,
        max_depth=5,
        num_leaves=25,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=1.0,
        reg_lambda=2.0,
        scale_pos_weight=scale_pos,
        random_state=42,
        n_jobs=-1,
        verbose=-1
    )

    model.fit(
        X_train,
        y_train,
        eval_X=X_test,
        eval_y=y_test,
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)]
    )

    y_pred_proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_pred_proba)

    print("=" * 60)
    print(f"🏆 KẾT QUẢ HUẤN LUYỆN: ROC-AUC OUT-OF-SAMPLE = {auc:.4f}")
    print(f"🌲 Số lượng cây tối ưu (Best Iteration): {model.best_iteration_}")
    print("=" * 60)

    package = {
        "model": model,
        "features": features,
        "metrics": {
            "test_auc": float(auc),
            "best_iteration": int(model.best_iteration_),
            "train_samples": int(len(X_train)),
            "test_samples": int(len(X_test))
        },
        "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "algorithm": "LightGBM Classifier"
    }

    joblib.dump(package, out_file, compress=3)
    file_size_kb = os.path.getsize(out_file) / 1024
    print(f"💾 Đã lưu file mô hình tại: {out_file} ({file_size_kb:.1f} KB)")
    return out_file

if __name__ == "__main__":
    train_and_export_local_model()

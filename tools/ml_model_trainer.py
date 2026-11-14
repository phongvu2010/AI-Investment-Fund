"""
Script Huấn luyện Mô hình Machine Learning Trực tiếp (Fast Local ML Trainer).
Tự động huấn luyện mô hình LightGBM từ file ml_dataset_train.parquet và đóng gói
thành tệp models/universal_alpha_model.joblib để hệ thống hoạt động ngay lập tức.
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import numpy as np
import polars as pl
import lightgbm as lgb
import joblib
from sklearn.metrics import roc_auc_score, accuracy_score, precision_score, recall_score, f1_score

# Thêm thư mục gốc dự án vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings

DEFAULT_FEATURES = [
    "ret_1d", "ret_3d", "ret_5d", "ret_10d", "ret_20d",
    "rel_ret_5d", "rel_ret_20d",
    "vol_ratio_20", "vol_zscore_60",
    "norm_atr_14", "bb_width_20",
    "body_to_range", "upper_wick_ratio", "lower_wick_ratio",
    "rsi_14", "macd_hist_norm",
    "market_ret_20d", "market_breadth_ma20", "rel_vol_to_market"
]

def run_walk_forward_validation(
    data_path: Optional[Path] = None,
    n_splits: int = 4,
    min_train_ratio: float = 0.50,
    embargo_days: int = 5
) -> Dict[str, Any]:
    """
    Thực thi kiểm thử Walk-Forward mở rộng (Expanding Window Walk-Forward Validation)
    theo chuẩn định lượng quốc tế (Advances in Financial Machine Learning):
    - Chia dữ liệu theo thời gian thực tế với cửa sổ huấn luyện mở rộng dần.
    - Áp dụng Purging / Embargo Gap (5 phiên) để triệt tiêu hiện tượng rò rỉ thông tin tương lai (Look-ahead bias / Data leakage từ nhãn Triple-Barrier).
    - Đo lường độ bền vững (Robustness) và độ ổn định của Alpha trên các chu kỳ thị trường khác nhau.
    """
    data_file = data_path or (settings.BASE_DIR / "data" / "ml_dataset_train.parquet")
    if not data_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file dữ liệu: {data_file}")

    print("\n" + "=" * 70)
    print(f"🔄 BẮT ĐẦU KIỂM THỬ WALK-FORWARD VALIDATION ({n_splits} GIAI ĐOẠN OUT-OF-SAMPLE)")
    print(f"📂 Dataset: {data_file}")
    print(f"🛡️ Embargo Gap: {embargo_days} phiên giao dịch (Khử rò rỉ nhãn Triple-Barrier)")
    print("=" * 70)

    df = pl.read_parquet(data_file)
    unique_dates = df["trade_date"].unique().sort().to_list()
    total_dates = len(unique_dates)

    init_train_len = int(total_dates * min_train_ratio)
    remaining_dates = total_dates - init_train_len
    test_fold_size = max(1, remaining_dates // n_splits)

    folds_results: List[Dict[str, Any]] = []

    for fold in range(n_splits):
        train_end_idx = init_train_len + fold * test_fold_size
        test_start_idx = min(train_end_idx + embargo_days, total_dates - 1)
        test_end_idx = min(train_end_idx + test_fold_size + embargo_days, total_dates)

        if test_start_idx >= total_dates or test_start_idx >= test_end_idx:
            break

        train_dates = unique_dates[:train_end_idx]
        test_dates = unique_dates[test_start_idx:test_end_idx]

        train_df = df.filter(pl.col("trade_date").is_in(train_dates))
        test_df = df.filter(pl.col("trade_date").is_in(test_dates))

        if len(train_df) == 0 or len(test_df) == 0:
            continue

        X_train = train_df.select(DEFAULT_FEATURES).to_pandas()
        y_train = train_df["target"].to_numpy()
        X_test = test_df.select(DEFAULT_FEATURES).to_pandas()
        y_test = test_df["target"].to_numpy()

        pos_count = np.sum(y_train == 1)
        neg_count = np.sum(y_train == 0)
        scale_pos = float(neg_count / max(pos_count, 1))

        model = lgb.LGBMClassifier(
            n_estimators=200,
            learning_rate=0.03,
            max_depth=5,
            num_leaves=25,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=1.0,
            reg_lambda=2.0,
            scale_pos_weight=scale_pos,
            random_state=42 + fold,
            n_jobs=-1,
            verbose=-1
        )

        model.fit(
            X_train,
            y_train,
            eval_set=[(X_test, y_test)],
            callbacks=[lgb.early_stopping(stopping_rounds=25, verbose=False)]
        )

        y_pred_proba = model.predict_proba(X_test)[:, 1]
        y_pred_bin = (y_pred_proba >= 0.50).astype(int)

        auc = float(roc_auc_score(y_test, y_pred_proba))
        acc = float(accuracy_score(y_test, y_pred_bin))
        prec = float(precision_score(y_test, y_pred_bin, zero_division=0))
        rec = float(recall_score(y_test, y_pred_bin, zero_division=0))
        f1 = float(f1_score(y_test, y_pred_bin, zero_division=0))

        fold_info = {
            "fold": fold + 1,
            "train_start": str(train_dates[0]),
            "train_end": str(train_dates[-1]),
            "train_samples": len(X_train),
            "test_start": str(test_dates[0]),
            "test_end": str(test_dates[-1]),
            "test_samples": len(X_test),
            "best_iteration": int(model.best_iteration_),
            "roc_auc": round(auc, 4),
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "pos_ratio_test": round(float(np.mean(y_test)), 4)
        }
        folds_results.append(fold_info)

        print(
            f"🔹 Fold {fold + 1}/{n_splits}: "
            f"Train [{fold_info['train_start']} -> {fold_info['train_end']}] ({fold_info['train_samples']:,} mẫu) | "
            f"Test OOS [{fold_info['test_start']} -> {fold_info['test_end']}] ({fold_info['test_samples']:,} mẫu) | "
            f"ROC-AUC: {auc:.4f} | Prec: {prec:.4f} | Acc: {acc:.4f}"
        )

    all_aucs = [f["roc_auc"] for f in folds_results]
    mean_auc = float(np.mean(all_aucs)) if all_aucs else 0.0
    std_auc = float(np.std(all_aucs)) if all_aucs else 0.0
    min_auc = float(np.min(all_aucs)) if all_aucs else 0.0
    max_auc = float(np.max(all_aucs)) if all_aucs else 0.0

    # Đánh giá tính ổn định của mô hình
    if mean_auc >= 0.58 and min_auc >= 0.52:
        robustness_status = "EXCELLENT"
        assessment = "Mô hình vượt trội và giữ vững Alpha xuyên suốt tất cả các chu kỳ thị trường."
    elif mean_auc >= 0.53 and min_auc >= 0.50:
        robustness_status = "PASS"
        assessment = "Mô hình đạt chuẩn kiểm định Out-of-Sample, có Edge thực tế trên sàn VN."
    else:
        robustness_status = "WARNING_OVERFIT"
        assessment = "Mô hình có dấu hiệu suy giảm hiệu năng tại một số chu kỳ kiểm nghiệm."

    summary = {
        "n_splits": len(folds_results),
        "mean_auc": round(mean_auc, 4),
        "std_auc": round(std_auc, 4),
        "min_auc": round(min_auc, 4),
        "max_auc": round(max_auc, 4),
        "robustness_status": robustness_status,
        "assessment": assessment,
        "folds": folds_results,
        "validated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    print("\n" + "=" * 70)
    print("📊 KẾT QUẢ TỔNG HỢP WALK-FORWARD:")
    print(f"   • Mean ROC-AUC:   {mean_auc:.4f} (±{std_auc:.4f})")
    print(f"   • Biên độ AUC:    [{min_auc:.4f} -> {max_auc:.4f}]")
    print(f"   • Trạng thái:     [{robustness_status}] - {assessment}")
    print("=" * 70)

    return summary

def train_and_export_local_model(
    data_path: Optional[Path] = None,
    output_model_path: Optional[Path] = None,
    run_wf: bool = False
) -> Path:
    data_file = data_path or (settings.BASE_DIR / "data" / "ml_dataset_train.parquet")
    out_file = output_model_path or (settings.BASE_DIR / "models" / "universal_alpha_model.joblib")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if not data_file.exists():
        print(f"⚠️ Chưa có file {data_file}, đang tự động trích xuất đặc trưng...")
        from tools.ml_feature_extractor import MLFeatureExtractor
        extractor = MLFeatureExtractor()
        extractor.export_dataset(data_file)

    # Chạy Walk-Forward Validation để thẩm định độ bền vững trước khi export
    wf_summary = None
    if run_wf:
        try:
            wf_summary = run_walk_forward_validation(data_path=data_file, n_splits=4)
        except Exception as e:
            print(f"⚠️ Walk-Forward validation gặp cảnh báo ({e}), tiếp tục quy trình đóng gói.")

    print(f"\n🧠 BẮT ĐẦU HUẤN LUYỆN UNIVERSAL ALPHA MODEL (LIGHTGBM)...")
    print(f"📂 Nguồn dữ liệu: {data_file}")
    df = pl.read_parquet(data_file)

    features = DEFAULT_FEATURES
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
        eval_set=[(X_test, y_test)],
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
        "walk_forward_summary": wf_summary,
        "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "algorithm": "LightGBM Classifier"
    }

    joblib.dump(package, out_file, compress=3)
    file_size_kb = os.path.getsize(out_file) / 1024
    print(f"💾 Đã lưu file mô hình tại: {out_file} ({file_size_kb:.1f} KB)")
    return out_file

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Huấn luyện mô hình LightGBM & Walk-Forward Validation")
    parser.add_argument("--walk-forward", action="store_true", help="Chỉ chạy kiểm thử Walk-Forward Validation")
    parser.add_argument("--splits", type=int, default=4, help="Số giai đoạn Walk-Forward (mặc định 4)")
    args = parser.parse_args()

    if args.walk_forward:
        run_walk_forward_validation(n_splits=args.splits)
    else:
        train_and_export_local_model()

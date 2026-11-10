"""
Backend API Server cho Web Dashboard (FastAPI).
Cung cấp dữ liệu thời gian thực từ SQLite & Parquet hoàn toàn miễn phí (0 Token).
"""

import sys
from pathlib import Path
from datetime import date
from typing import Optional, List, Dict, Any
import json

# Tự động thêm thư mục gốc dự án vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings
from database.db_manager import DatabaseManager
from tools.parquet_manager import ParquetMarketDataManager

app = FastAPI(
    title="AI Personal Investment Fund API",
    description="Backend cung cấp dữ liệu cho Web Dashboard 0 Token",
    version="1.0.0"
)

# Cho phép CORS để React frontend gọi API mượt mà
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = DatabaseManager()
parquet_mgr = ParquetMarketDataManager()

# Mount thư mục reports để xem trực tiếp biểu đồ HTML Plotly của vn-backtest
reports_dir = settings.BASE_DIR / "dashboard" / "reports"
reports_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/reports", StaticFiles(directory=str(reports_dir)), name="reports")

# ==========================================
# Pydantic Request Models
# ==========================================
class FillOrderRequest(BaseModel):
    ticker: str
    action: str = "BUY"
    price: float
    volume: int
    trade_date: Optional[str] = None
    notes: Optional[str] = "Nhập lệnh từ Web Dashboard"

class CloseNavRequest(BaseModel):
    trade_date: Optional[str] = None
    notes: Optional[str] = "Chốt sổ thủ công từ Dashboard"

class OptimizeStrategyRequest(BaseModel):
    strategy_id: str = "vsa-momentum"
    ticker: str = "HPG"

# ==========================================
# API ENDPOINTS
# ==========================================
@app.get("/api/health")
def health_check():
    return {"status": "HEALTHY", "fund": "AI Personal Investment Fund", "currency": "VND"}

@app.get("/api/nav/summary")
def get_nav_summary():
    """Lấy số liệu tài sản và biến động NAV mới nhất (0 Token)"""
    nav = db.get_latest_nav()
    if not nav:
        nav = {
            "total_nav": settings.INITIAL_CAPITAL,
            "cash_balance": settings.INITIAL_CAPITAL,
            "stock_value": 0.0,
            "daily_pnl": 0.0,
            "daily_pnl_pct": 0.0,
            "cumulative_pnl": 0.0,
            "trade_date": date.today().strftime("%Y-%m-%d")
        }
    return nav

@app.get("/api/nav/history")
def get_nav_history(limit: int = 90):
    """Lấy chuỗi lịch sử NAV phục vụ vẽ biểu đồ đường cong vốn (Equity Curve)"""
    return db.get_nav_history(limit=limit)

@app.get("/api/portfolio")
def get_portfolio():
    """Lấy danh mục cổ phiếu đang nắm giữ kèm lãi/lỗ và tỷ trọng"""
    return db.get_portfolio()

@app.get("/api/orders")
def get_orders(limit: int = 50):
    """Lấy danh sách sổ lệnh mua/bán và trạng thái khớp"""
    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT order_id, ticker, action, order_type, proposed_price, proposed_volume,
                   executed_price, executed_volume, status, fee, tax, slippage_pct,
                   trade_date, created_at, executed_at, notes
            FROM order_history
            ORDER BY created_at DESC
            LIMIT ?;
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

@app.get("/api/reports")
def get_strategy_reports():
    """Lấy danh sách các báo cáo chiến lược đã backtest với vn-backtest"""
    skills_dir = settings.BASE_DIR / ".agent" / "skills"
    reports = []

    if skills_dir.exists():
        for s_dir in skills_dir.iterdir():
            if s_dir.is_dir() and s_dir.name.startswith("strategy-"):
                status_file = s_dir / "status.json"
                if status_file.exists():
                    try:
                        with open(status_file, "r", encoding="utf-8") as f:
                            info = json.load(f)
                            # Trích xuất tên file HTML an toàn độc lập hệ điều hành
                            raw_report = info.get("html_report", "")
                            html_name = info.get("html_filename") or Path(raw_report).name
                            if not html_name or html_name == ".":
                                html_name = f"{info['title'].lower().replace(' ', '_')}.html"
                            info["html_url"] = f"/static/reports/{html_name}"
                            reports.append(info)
                    except Exception:
                        pass
    return reports

@app.post("/api/orders/fill")
def submit_fill_order(req: FillOrderRequest):
    """Thực hiện nhập bù / ghi nhận lệnh khớp từ Web Dashboard"""
    try:
        order_id = db.record_retroactive_fill(
            ticker=req.ticker.upper(),
            action=req.action.upper(),
            executed_price=req.price,
            executed_volume=req.volume,
            trade_date=req.trade_date,
            notes=req.notes
        )
        return {"status": "SUCCESS", "order_id": order_id, "message": f"Đã ghi nhận khớp {req.ticker}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/nav/close")
def trigger_close_nav(req: CloseNavRequest):
    """Kích hoạt chốt sổ NAV ngày (Mark-to-Market) bằng giá đóng cửa mới nhất"""
    t_date = req.trade_date or date.today().strftime("%Y-%m-%d")
    latest_prices = parquet_mgr.get_latest_close_prices()

    res = db.close_daily_nav(
        trade_date=t_date,
        current_prices=latest_prices,
        notes=req.notes
    )
    return {"status": "SUCCESS", "nav_report": res}

@app.post("/api/strategies/optimize")
def trigger_optimize_strategy(req: OptimizeStrategyRequest):
    """Kích hoạt Động cơ Tự học hỏi & Tiến hóa tối ưu hóa chiến lược"""
    try:
        from tools.strategy_optimizer import StrategyOptimizerEngine
        engine = StrategyOptimizerEngine()
        res = engine.auto_heal_vsa_strategy(ticker=req.ticker)
        return {"status": "SUCCESS", "result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ml/rankings")
def get_ml_market_rankings(top_n: int = 10):
    """Lấy Bảng xếp hạng Điểm số Alpha (ML Score) toàn thị trường"""
    try:
        from tools.ml_predictor import UniversalAlphaPredictor
        predictor = UniversalAlphaPredictor()
        rankings = predictor.get_market_rankings(top_n=top_n)
        return {
            "status": "SUCCESS",
            "model_algorithm": getattr(predictor, "algorithm", "LightGBM"),
            "trained_at": predictor.trained_at,
            "rankings": rankings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ml/score/{ticker}")
def get_ml_ticker_score(ticker: str):
    """Chấm điểm ML Score chi tiết cho một mã cổ phiếu"""
    try:
        from tools.ml_predictor import UniversalAlphaPredictor
        predictor = UniversalAlphaPredictor()
        score = predictor.predict_score(ticker)
        features = predictor._extract_live_features_for_ticker(ticker.upper()) or {}
        return {
            "ticker": ticker.upper(),
            "ml_score": score,
            "features": features
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ml/model/info")
def get_ml_model_info():
    """Lấy thông tin siêu dữ liệu của Model ML hiện tại & trạng thái file dataset"""
    try:
        from tools.ml_predictor import UniversalAlphaPredictor
        predictor = UniversalAlphaPredictor()
        
        csv_file = settings.BASE_DIR / "data" / "ml_dataset_train.csv"
        csv_exists = csv_file.exists()
        csv_size_mb = round(csv_file.stat().st_size / (1024 * 1024), 2) if csv_exists else 0.0
        
        parquet_file = settings.BASE_DIR / "data" / "ml_dataset_train.parquet"
        parquet_exists = parquet_file.exists()
        
        sample_count = 0
        if parquet_exists:
            import polars as pl
            try:
                sample_count = len(pl.read_parquet(parquet_file))
            except Exception:
                pass
        
        return {
            "status": "SUCCESS",
            "algorithm": getattr(predictor, "algorithm", "LightGBM Classifier"),
            "trained_at": predictor.trained_at,
            "metrics": predictor.metrics,
            "model_path": "models/universal_alpha_model.joblib",
            "dataset": {
                "csv_exists": csv_exists,
                "csv_size_mb": csv_size_mb,
                "parquet_exists": parquet_exists,
                "sample_count": sample_count
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ml/extract")
def trigger_ml_feature_extraction():
    """Kích hoạt Trích xuất 15 Đặc trưng Kỹ thuật & Gán nhãn Triple-Barrier từ Parquet"""
    try:
        from tools.ml_feature_extractor import MLFeatureExtractor
        extractor = MLFeatureExtractor()
        output_parquet = settings.BASE_DIR / "data" / "ml_dataset_train.parquet"
        extractor.export_dataset(output_parquet, export_csv=True)
        
        import polars as pl
        df = pl.read_parquet(output_parquet)
        total_samples = len(df)
        pos_count = int(df.filter(pl.col("target") == 1).shape[0])
        neg_count = int(df.filter(pl.col("target") == 0).shape[0])
        
        return {
            "status": "SUCCESS",
            "message": f"Đã trích xuất thành công {total_samples:,} mẫu nến huấn luyện!",
            "total_samples": total_samples,
            "pos_count": pos_count,
            "neg_count": neg_count,
            "pos_pct": round((pos_count / max(total_samples, 1)) * 100.0, 2),
            "csv_ready": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ml/dataset/download")
def download_ml_dataset_csv():
    """Tải trực tiếp tệp ml_dataset_train.csv về máy tính để upload lên Kaggle"""
    csv_file = settings.BASE_DIR / "data" / "ml_dataset_train.csv"
    if not csv_file.exists():
        raise HTTPException(status_code=404, detail="Chưa có tệp ml_dataset_train.csv. Vui lòng bấm Trích xuất đặc trưng trước.")
    return FileResponse(
        path=str(csv_file),
        filename="ml_dataset_train.csv",
        media_type="text/csv"
    )

@app.post("/api/ml/model/upload")
async def upload_ml_model_file(file: UploadFile = File(...)):
    """Tải lên tệp model (.joblib) đã huấn luyện trên Kaggle/Colab vào hệ thống"""
    if not file.filename.endswith(".joblib"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận tệp có định dạng .joblib!")
    
    target_path = settings.BASE_DIR / "models" / "universal_alpha_model.joblib"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    contents = await file.read()
    if len(contents) < 500:
        raise HTTPException(status_code=400, detail="Tệp tải lên không hợp lệ hoặc quá nhỏ!")
        
    with open(target_path, "wb") as f:
        f.write(contents)
        
    # Buộc nạp lại model vào RAM
    from tools.ml_predictor import UniversalAlphaPredictor
    predictor = UniversalAlphaPredictor()
    predictor.reload_model()
    
    return {
        "status": "SUCCESS",
        "message": f"Đã cập nhật mô hình {file.filename} thành công!",
        "trained_at": predictor.trained_at,
        "algorithm": getattr(predictor, "algorithm", "LightGBM Classifier"),
        "metrics": predictor.metrics
    }

# Mount thư mục build của React frontend (nếu đã build) để phục vụ Dashboard trực tiếp tại root URL
dist_dir = settings.BASE_DIR / "dashboard" / "frontend" / "dist"
if dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard.api:app", host="0.0.0.0", port=8000, reload=True)

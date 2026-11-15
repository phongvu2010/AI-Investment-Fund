# ====================================================================
# STAGE 1: BUILD FRONTEND (REACT + VITE + TAILWIND CSS)
# ====================================================================
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

COPY apps/web/package*.json ./
RUN npm install

COPY apps/web/ ./
RUN npm run build

# ====================================================================
# STAGE 2: PYTHON BACKEND & FULL SYSTEM RUNTIME
# ====================================================================
FROM python:3.12-slim-bookworm

# Thiết lập múi giờ Việt Nam (UTC+7)
ENV TZ=Asia/Ho_Chi_Minh
ENV PYTHONUNBUFFERED=1
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Cài đặt công cụ biên dịch tối thiểu cho Numba & Polars
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Python packages từ requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn dự án
COPY . .

# Copy bản build tĩnh của React từ Stage 1 sang thư mục phục vụ của FastAPI
COPY --from=frontend-builder /app/frontend/dist /app/apps/web/dist

# Expose cổng Web Dashboard & API
EXPOSE 8000

# Lệnh mặc định khi chạy container: Khởi chạy Web Dashboard API
CMD ["python", "apps/api/main.py"]

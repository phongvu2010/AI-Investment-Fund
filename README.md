# 🏛️ QUỸ ĐẦU TƯ CHỨNG KHOÁN CÁ NHÂN TỰ TRỊ (AI INVESTMENT FUND)
### Autonomous Multi-Agent Hedge Fund • Vietnam Stock Market (HOSE / HNX / UPCOM)

Hệ thống Quỹ đầu tư định lượng cá nhân vận hành tự động theo mô hình **Tổ chức Đa Tác tử (Multi-Agent Organization)**, kết hợp động cơ Backtest chuẩn sàn Việt Nam (`vn-backtest`), Cơ sở dữ liệu SQLite Mark-to-Market, Tương tác di động qua Telegram Bot, Web Dashboard Zero-Token (FastAPI + React 19) và Hạ tầng Machine Learning (LightGBM).

---

## 📑 MỤC LỤC
1. [Kiến Trúc & Triết Lý Vận Hành](#1-kiến-trúc--triết-lý-vận-hành)
2. [Cấu Trúc Thư Mục Hệ Thống](#2-cấu-trúc-thư-mục-hệ-thống)
3. [Cài Đặt & Chuẩn Bị Môi Trường](#3-cài-đặt--chuẩn-bị-môi-trường)
4. [Cấu Hình Hệ Thống (.env)](#4-cấu-hình-hệ-thống-env)
5. [Quy Trình Vận Hành Hằng Ngày (Daily SOPs)](#5-quy-trình-vận-hành-hằng-ngày-daily-sops)
6. [Phòng Thí Nghiệm Chiến Lược (Backtest & Strategy Lab)](#6-phòng-thí-nghiệm-chiến-lược-backtest--strategy-lab)
7. [Động Cơ Tự Học Hỏi & Tối Ưu Hóa (Self-Healing)](#7-động-cơ-tự-học-hỏi--tối-ưu-hóa-self-healing)
8. [Hạ Tầng Machine Learning (Universal Quant Alpha Model)](#8-hạ-tầng-machine-learning-universal-quant-alpha-model)
9. [Khởi Chạy Web Dashboard & Docker Compose](#9-khởi-chạy-web-dashboard--docker-compose)
10. [Hệ Thống Kế Toán Quỹ & Quản Trị Đa Tài Khoản (Historical Vault)](#10-hệ-thống-kế-toán-quỹ--quản-trị-đa-tài-khoản-historical-vault)
11. [Bộ Kiểm Thử Hệ Thống (Test Suites)](#11-bộ-kiểm-thử-hệ-thống-test-suites)

---

## 1. KIẾN TRÚC & TRIẾT LÝ VẬN HÀNH

### Mô hình Tranh biện Đối kháng (Adversarial Multi-Agent Framework)
Không để một AI duy nhất ra quyết định. Mọi đề xuất giải ngân đều phải trải qua cuộc tranh luận gay gắt:
* **Phe Bò (Bull Advocate):** Tìm kiếm tiềm năng tăng trưởng, xung lượng giá và sự bùng nổ của dòng tiền.
* **Phe Gấu / Đội Đỏ (Bear Advocate - Red Team):** Bới lông tìm vết, đào bới rủi ro nợ vay, thanh khoản, cản kỹ thuật và các bẫy giá giả (Bull-traps).
* **Giám đốc Rủi ro (CRO):** Nắm quyền Phủ quyết Tuyệt đối (**VETO Power**). Nếu vi phạm bất kỳ hạn mức rủi ro nào (sụt giảm vốn, thiếu thanh khoản, tỷ trọng quá lớn), lệnh bị hủy lập tức.
* **Giám đốc Đầu tư (CIO):** Tổng hợp luận điểm hai chiều, cân nhắc xác suất và ký quyết định đầu tư (Investment Decision Memo).
* **Kế toán Quỹ (Accountant):** Chốt sổ NAV Mark-to-Market hằng ngày, tính toán chính xác thuế (0.1%), phí (0.15%), trượt giá và quyền cổ tức.
* **Kiểm toán viên (Auditor):** Hậu kiểm, khám nghiệm thất bại (Post-Mortem) khi vị thế chạm ngưỡng cắt lỗ (-7.0%) để cập nhật quy tắc phòng thủ vào Hiến pháp Quỹ.

### Triết lý Vận hành 0 Token (Zero-Token Architecture)
* 100% các tác vụ tính toán toán học, chỉ báo kỹ thuật, quét dữ liệu nến 5 năm, backtest, Mark-to-Market NAV, xếp hạng Machine Learning và phục vụ Web Dashboard đều chạy bằng **Python + DuckDB + Polars + SQLite** nội bộ.
* **Hoàn toàn miễn phí, tiêu tốn 0 token LLM.**

---

## 2. CẤU TRÚC THƯ MỤC HỆ THỐNG

```
AI Investment Fund/
├── .agent/                       # Não bộ tổ chức Multi-Agent
│   ├── agents/                   # Nhân sự AI (CIO, CRO, Bull, Bear, Accountant...)
│   ├── rules/                    # Hiến pháp Quỹ & Hạn mức rủi ro
│   ├── workflows/                # Quy trình SOP chuẩn (Morning, Debate, EOD, Post-Mortem)
│   ├── skills/                   # Kho Kỹ năng Chiến lược đầu tư (Agent Skills)
│   └── journals/                 # Nhật ký Tiến hóa & Khám nghiệm thất bại (Post-Mortem Memos)
├── backtest/                     # Động cơ Backtest chuẩn sàn VN (vn-backtest)
│   ├── runner.py                 # Bộ thực thi kiểm thử 5 năm & xuất biểu đồ tương tác HTML
│   ├── report_adapter.py         # Thẩm định Hội đồng CRO & biên tập Markdown
│   └── strategy_template.py      # Lớp cơ sở BaseFundStrategy & chỉ báo Polars
├── config/                       # Cấu hình hệ thống (settings.py)
├── dashboard/                    # Web Dashboard Zero-Token
│   ├── api.py                    # Backend REST API (FastAPI)
│   ├── reports/                  # Thư mục lưu biểu đồ Plotly tương tác HTML
│   └── frontend/                 # Giao diện người dùng (React 19 + Vite + Tailwind CSS)
├── data/                         # Kho dữ liệu định lượng Parquet
│   ├── market_history_5y.parquet # Dữ liệu lịch sử 5 năm toàn thị trường (ZSTD nén)
│   └── ml_dataset_train.parquet  # Ma trận 15 đặc trưng & nhãn Triple-Barrier ML
├── database/                     # Kho lưu trữ SQLite bất biến
│   ├── schema.sql                # Định nghĩa 6 bảng CSDL chuẩn mực
│   ├── fund_vault.db             # File SQLite lưu sổ lệnh, portfolio, NAV daily
│   └── db_manager.py             # Kế toán giao dịch, tính giá bình quân gia quyền
├── interfaces/                   # Kênh giao tiếp Người - Máy
│   ├── telegram_bot.py           # Bot Telegram tương tác 1 chạm & bóc tách /fill
│   └── message_templates.py      # Mẫu tin nhắn Tờ trình đầu tư 2 chiều Bull/Bear
├── models/                       # Thư mục chứa mô hình Machine Learning (.joblib)
├── notebooks/                    # Jupyter Notebook huấn luyện trên Kaggle / Colab
│   └── kaggle_train_lightgbm.ipynb
├── tests/                        # Toàn bộ Test Suites kiểm thử tự động
├── tools/                        # Công cụ nghiệp vụ tự động hóa
│   ├── bigquery_sync.py          # Đồng bộ BigQuery -> Parquet 5 năm & nến ngày
│   ├── parquet_manager.py        # Truy vấn Parquet siêu tốc bằng DuckDB & Polars
│   ├── strategy_generator.py     # Đóng gói chiến lược thành Agent Skill chuẩn
│   ├── strategy_optimizer.py     # Động cơ Tự học hỏi, Sửa sai & Tối ưu hóa tham số
│   ├── ml_feature_extractor.py   # Trích xuất 15 đặc trưng kỹ thuật & nhãn 3 rào cản
│   ├── ml_model_trainer.py       # Huấn luyện nhanh Universal Alpha Model (LightGBM)
│   ├── ml_predictor.py           # Động cơ suy luận chấm điểm Alpha Score < 0.005s
│   └── scheduler.py              # Bộ lập lịch tự động kích hoạt cronjob hàng ngày
├── main.py                       # Bộ điều phối trung tâm (CLI Orchestrator)
├── Dockerfile                    # Đóng gói Container độc lập môi trường
├── docker-compose.yml            # Khởi chạy toàn bộ hệ thống bằng 1 câu lệnh
└── requirements.txt              # Danh sách thư viện Python
```

---

## 3. CÀI ĐẶT & CHUẨN BỊ MÔI TRƯỜNG

### Cách 1: Chạy trực tiếp trên máy vật lý (macOS / Linux / Windows WSL2)

1. **Yêu cầu:** Python 3.11 hoặc 3.12, Node.js v18+.
2. **Cài đặt thư viện Python:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Trên Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Cài đặt và Build Frontend Dashboard:**
   ```bash
   cd dashboard/frontend
   npm install
   npm run build
   cd ../..
   ```

### Cách 2: Khởi chạy bằng Docker Compose (Khuyên dùng cho Máy chủ / VPS)
Không cần cài đặt Python hay Node.js trên máy chủ, Docker sẽ tự động đóng gói toàn bộ:
```bash
docker compose up -d --build
```

---

## 4. CẤU HÌNH HỆ THỐNG (.env)

Tạo file `.env` từ file mẫu `.env.example`:
```bash
cp .env.example .env
```
Chỉnh sửa các tham số trong file `.env`:
```ini
# Vốn & Phí giao dịch
INITIAL_CAPITAL=1000000000.0   # Vốn khởi điểm: 1 tỷ VND
BROKER_FEE_RATE=0.0015         # Phí môi giới: 0.15%
SELL_TAX_RATE=0.0010           # Thuế bán chứng khoán: 0.10%

# Telegram Bot (Nhận đề xuất lệnh & Báo cáo NAV)
TELEGRAM_BOT_TOKEN="your_bot_token_from_botfather"
TELEGRAM_CHAT_ID="your_telegram_chat_id"

# Google BigQuery Data Warehouse
GCP_PROJECT_ID="ai-trading-system-496014"
GCP_DATASET="vn_stock"
GCP_RAW_PRICE_TABLE="raw_price"
GCP_ADJ_PRICE_TABLE="adj_price"
GOOGLE_APPLICATION_CREDENTIALS="credentials/service_account.json"
```

---

## 5. QUY TRÌNH VẬN HÀNH HẰNG NGÀY (DAILY SOPS)

> 💡 **HỆ THỐNG MẶC ĐỊNH CHẠY TỰ ĐỘNG 100% (BẠN KHÔNG CẦN CHẠY THỦ CÔNG MỖI NGÀY):**
> Khi bạn khởi động hệ thống qua **Docker Compose** (`docker compose up -d`) hoặc bật cỗ máy lập lịch (`python3 tools/scheduler.py`), container `fund-scheduler` sẽ chạy ngầm 24/7 và **tự động thức dậy thực thi đúng giờ** (từ Thứ 2 đến Thứ 6):
> * **08:00 AM:** Tự động tạo bản tin Morning Briefing & bắn danh sách cổ phiếu đột biến Volume lên Telegram.
> * **15:30 PM:** Tự động chốt sổ kế toán NAV (Mark-to-Market) và gửi báo cáo biến động tài sản lên Telegram.
> * **20:00 PM:** Tự động rà soát và nhắc nhở đối soát các lệnh chờ khớp trong ngày.
> * **21:00 PM:** Tự động kết nối BigQuery tải nến mới nhất của phiên về nối vào file Parquet 5 năm.

---

### Chế độ Kích Hoạt Thủ Công Theo Nhu Cầu (On-Demand / Manual Triggers)
Các câu lệnh dưới đây **chỉ dùng khi bạn muốn chủ động can thiệp**, chạy thử nghiệm ngoài giờ hoặc kích hoạt cuộc họp phân tích cho một mã cổ phiếu bất kỳ:

#### 1. Buổi Sáng (08h45) - Morning Briefing Thủ Công
Chạy quét thị trường và kiểm tra trạng thái quỹ ngay lập tức:
```bash
python3 main.py --workflow morning
```
* Báo cáo tài sản ròng NAV và danh mục đang nắm giữ.
* DuckDB quét các mã có khối lượng giao dịch đột biến (Volume > 1.5x) phiên trước đó.
* Machine Learning xếp hạng các mã có điểm số Alpha cao nhất.

#### 2. Phiên Giao Dịch (09h00 - 14h45) - Hội Đồng Tranh Biện & Phát Lệnh Thủ Công
Kích hoạt tranh biện đa tác tử và gửi Tờ trình đầu tư đến điện thoại qua Telegram cho mã bất kỳ:
```bash
python3 main.py --workflow debate --ticker HPG
```
* **Phe Bò (Bull):** Đưa ra luận điểm tăng giá.
* **Phe Gấu (Bear):** Chỉ ra các rủi ro cần phòng vệ.
* **CRO & CIO:** Duyệt lệnh và gửi thông báo kèm 2 nút bấm lên Telegram:
  - `[✅ Đã đặt lệnh chờ]`: Đánh dấu trạng thái `SUBMITTED` vào sổ lệnh.
  - `[❌ Bỏ qua / Hủy lệnh]`: Hủy đề xuất.

#### Cơ chế Nhập Bù Lệnh Khớp Thực Tế (`/fill`)
Bạn đặt lệnh trực tiếp trên app công ty chứng khoán (VPS, SSI, TCBS...). Khi lệnh khớp thực tế, bạn chỉ cần nhắn vào Telegram Bot:
```text
/fill HPG 5000 28.2
```
Hoặc nhắn bằng văn bản tự nhiên:
```text
khớp HPG 5000 giá 28.2
mua SSI 3000 32.5
```
Hệ thống sẽ tự động bóc tách, trừ tiền mặt, cập nhật số dư cổ phiếu và tính lại giá vốn bình quân gia quyền.

#### 3. Buổi Tối (20h30 - 21h00) - Đồng Bộ Dữ Liệu & Chốt Sổ NAV Tự Động / 1-Click
1. **Đồng bộ giá từ BigQuery 1-Click trên Web Dashboard:**
   Bạn chỉ cần mở Web Dashboard và bấm nút **`[Đồng Bộ Giá BigQuery]`** trên thanh Header. Hệ thống sẽ:
   * Tự động kéo nến đóng cửa thực tế mới nhất từ Google BigQuery (`raw_price`).
   * Tự động chốt sổ tuần tự cả 2 phiên $T-1$ và $T$, đảm bảo **Biến Động Trong Ngày (Daily PnL)** phản ánh chính xác 100% mức tăng/giảm thực tế của thị trường.
   * Tự động định giá cổ phiếu treo sàn (`FLC`) về `0,00 đ` theo nguyên tắc thận trọng.
2. **Hoặc kích hoạt qua dòng lệnh:**
   ```bash
   python3 tools/bigquery_sync.py --mode daily
   python3 main.py --workflow eod
   ```
   *(Nếu mới cài đặt lần đầu và chưa có file nến 5 năm, chạy: `python3 tools/bigquery_sync.py --mode full` hoặc `--mode demo`)*.

---

## 6. PHÒNG THÍ NGHIỆM CHIẾN LƯỢC (BACKTEST & STRATEGY LAB)

> 💡 **CƠ CHẾ VẬN HÀNH: BẠN RA Ý TƯỞNG (PROMPT) ➔ AI TỰ ĐỘNG LẬP TRÌNH & KIỂM ĐỊNH 100%**  
> Bạn **không bắt buộc phải biết code Python**. Toàn bộ quy trình từ chuyển hóa ý tưởng thành mã nguồn, chạy kiểm thử 5 năm, thẩm định rủi ro và đóng gói thành Kỹ năng AI (`Agent Skill`) đều được tự động hóa.

---

### HƯỚNG DẪN TẠO CHIẾN LƯỢC MỚI (DÀNH CHO NGƯỜI DÙNG)

Khi muốn nghiên cứu hoặc thử nghiệm một chiến lược đầu tư mới, bạn chỉ cần thực hiện theo **3 bước đơn giản** sau:

#### Bước 1: Nêu Ý Tưởng Bằng Ngôn Ngữ Tự Nhiên Với AI Assistant (Prompting)
Bạn chỉ cần mở khung chat và gửi yêu cầu bằng tiếng Việt theo một trong hai cách:

* **Cách A - Bạn đã có sẵn ý tưởng kỹ thuật cụ thể:**
  > *"Hãy tạo cho tôi chiến lược **Vượt Đỉnh 52 Tuần (52-Week High Breakout)** cho mã **HPG** và **SSI**. Điều kiện vào lệnh: Giá vượt đỉnh 52 tuần gần nhất kèm Volume > 1.3 lần trung bình 20 phiên và điểm ML Score >= 0.60. Thoát lệnh khi giá thủng đường MA20 hoặc cắt lỗ 7%. Chạy backtest 5 năm và đóng gói thành Skill giúp tôi."*

* **Cách B - Bạn muốn AI tự động đề xuất ý tưởng định lượng:**
  > *"Dựa trên kho dữ liệu Parquet 5 năm của nhóm VN30, hãy phân tích và đề xuất cho tôi 1 chiến lược theo trường phái Bắt đáy Quá bán (RSI Mean Reversion) đạt tiêu chuẩn Sharpe >= 1.20 và Max Drawdown <= 15%."*

---

#### Bước 2: AI Tự Động Thực Thi Toàn Bộ Quy Trình Kỹ Thuật (Trong 10-15 Giây)
Ngay sau khi nhận prompt, hệ thống AI sẽ tự động kích hoạt chuỗi tác vụ ngầm:
1. **Tự động viết mã Python:** Tạo lớp thuật toán kế thừa [`BaseFundStrategy`](backtest/strategy_template.py) với các chỉ báo vector hóa siêu tốc (SMA, EMA, RSI, Bollinger Bands, Volume Ratios).
2. **Tự động chạy `vn-backtest` 5 năm:** Mô phỏng khớp lệnh thực tế trên 1.250 phiên nến điều chỉnh, tuân thủ nghiêm ngặt chu kỳ thanh toán $T+2.5$, bước giá trần/sàn, lô chẵn 100, phí môi giới 0.15% và thuế bán 0.1%.
3. **Thẩm định Hội đồng Giám đốc Rủi ro (CRO Evaluation):** Đối chiếu kết quả định lượng với Hiến pháp Quỹ:
   - ✅ Sharpe Ratio $\ge 1.20$
   - ✅ Max Drawdown $\le 15.00\%$
   - ✅ Profit Factor $\ge 1.80$
   - ✅ Tổng số lệnh kiểm nghiệm $\ge 15$ lệnh (đảm bảo đủ mẫu thống kê)
4. **Tự động đóng gói thành Skill:** Lưu vào `.agent/skills/strategy-<tên-chiến-lược>/` gồm:
   - [`SKILL.md`](.agent/skills/strategy-vsa-momentum/SKILL.md): Bản mô tả quy tắc vào/ra lệnh cho các Agent đọc hiểu.
   - `backtest_report.md`: Báo cáo định lượng chi tiết và kết luận thẩm định của CRO.
   - `status.json`: Trạng thái thẩm định (`APPROVED_TIER_A`, `APPROVED_TIER_B`, hoặc `REJECTED`).
   - `dashboard/reports/<tên>.html`: Biểu đồ đường cong vốn (Equity Curve) Plotly tương tác trực quan.

---

#### Bước 3: Nếu Chiến Lược Bị CRO Từ Chối (`REJECTED`) ➔ Kích Hoạt Tự Học Sửa Sai
Nếu ý tưởng ban đầu chưa đạt chuẩn rủi ro (như Sharpe âm hoặc bị dính bẫy giá giả), bạn **không cần phải tự ngồi đoán mò tham số**. Hãy để Động cơ Tối ưu hóa tự động sửa sai:

```bash
python3 main.py --optimize <tên-chiến-lược> --ticker <mã-cổ-phiếu>
# Ví dụ:
python3 main.py --optimize vsa-momentum --ticker HPG
```
Cỗ máy [`tools/strategy_optimizer.py`](tools/strategy_optimizer.py) sẽ:
* Tự động quét toàn bộ lưới tham số (Grid Search / Bayes Optimization) qua `ParameterOptimizer`.
* Tìm ra bộ tham số có tỷ suất sinh lời tối ưu và sụt giảm vốn thấp nhất.
* Nâng cấp chiến lược lên phiên bản **v2.0** và viết bài học kinh nghiệm vào [`.agent/journals/`](.agent/journals/).

---

### DÀNH CHO DEVELOPERS / QUANTS MUỐN TỰ TAY VIẾT CODE PYTHON

Nếu bạn muốn tự tay lập trình logic chiến lược thay vì dùng prompt, bạn chỉ cần mở file [`backtest/strategy_template.py`](backtest/strategy_template.py) và viết theo mẫu chuẩn:

```python
from backtest.strategy_template import BaseFundStrategy, indicator_sma, indicator_rsi

class CustomAlphaStrategy(BaseFundStrategy):
    # Tham số cấu hình (có thể quét tối ưu hóa tự động)
    ma_period: int = 20
    vol_multiplier: float = 1.2

    def init(self):
        # 1. Đăng ký các chỉ báo kỹ thuật vector hóa bằng Polars
        self.ma_close = self.I(indicator_sma, length=self.ma_period, ticker="HPG")
        self.rsi14 = self.I(indicator_rsi, length=14, ticker="HPG")

    def next(self):
        # 2. Lấy dữ liệu phiên hiện tại (Bảo vệ Zero Look-Ahead Bias)
        close = self.get_close("HPG")
        vol = self.get_volume("HPG")
        ma_val = self.get_indicator(self.ma_close)
        ml_score = self.get_ml_score("HPG")  # Điểm số Machine Learning (0.00 - 1.00)

        # 3. Quản lý trạng thái vị thế & chu kỳ T+2.5
        holding_qty = self.get_holding_qty("HPG")
        sellable_qty = self.get_sellable_qty("HPG")

        # Điều kiện MUA: Vượt MA + Khối lượng xác nhận + ML Score khả quan
        if holding_qty == 0:
            if ma_val and close > ma_val and ml_score >= 0.65:
                # Phân bổ 20% NAV khả dụng (lô chẵn 100)
                alloc_cash = self.available_cash * 0.20
                shares = int((alloc_cash / close) // 100) * 100
                if shares >= 100:
                    self.buy("HPG", size=shares, note="Breakout + High ML Confidence")

        # Điều kiện BÁN: Đóng vị thế khi giá thủng MA (chỉ bán khi hàng đã về khả dụng)
        elif sellable_qty > 0:
            if ma_val and close < ma_val:
                self.sell("HPG", size=sellable_qty, note="Exit Signal")
```

Sau khi viết xong, bạn chỉ cần gọi [`tools/strategy_generator.py`](tools/strategy_generator.py) để hệ thống tự động chạy kiểm thử và đóng gói thành Skill:
```python
from tools.strategy_generator import StrategySkillPackage

pkg = StrategySkillPackage(strategy_id="custom-alpha", strategy_title="Custom Alpha Strategy")
pkg.deploy_and_backtest(
    strategy_class=CustomAlphaStrategy,
    tickers="HPG",
    description="Chiến lược giao dịch động lượng kết hợp bộ lọc xác suất ML.",
    entry_rules="Giá vượt SMA20 và ML Score >= 0.65.",
    exit_rules="Giá thủng SMA20 sau chu kỳ T+2.5."
)
```

---

## 7. ĐỘNG CƠ TỰ HỌC HỎI & TỐI ƯU HÓA (SELF-HEALING)

Khi một chiến lược bị CRO từ chối (`REJECTED`) hoặc dính cắt lỗ, hệ thống không bỏ cuộc mà kích hoạt **Vòng lặp Tiến hóa Tự động**:

```bash
python3 main.py --optimize vsa-momentum --ticker HPG
```
**Quy trình 4 bước tự động:**
1. **Chẩn đoán thất bại:** Phân tích nguyên nhân (Thiếu số lượng mẫu lệnh, Bẫy giá giả làm Sharpe âm, hay Thiếu cơ chế cắt lỗ làm sụt giảm vốn sâu).
2. **Quét không gian tham số:** Tự động kích hoạt `ParameterOptimizer` của `vn-backtest` để tìm kiếm bộ tham số tối ưu (Chu kỳ MA, hệ số Volume, xung lượng RSI).
3. **Tái đóng gói v2.0:** Tự động nâng cấp mã nguồn, cập nhật lại `status.json` và bảng đối sánh Trước/Sau trong `backtest_report.md`.
4. **Viết Post-Mortem Memo:** Đúc kết bài học kinh nghiệm và lưu vào thư mục `.agent/journals/`.

---

## 8. HẠ TẦNG MACHINE LEARNING (UNIVERSAL QUANT ALPHA MODEL)

Hệ thống tích hợp mô hình Machine Learning **Strategy-Agnostic (Không phụ thuộc chiến lược)** và hỗ trợ **Quản lý 100% Trực tiếp trên Web Dashboard (Không cần chạm vào code)**:

> 🌐 **GIAO DIỆN MACHINE LEARNING LAB TRÊN WEB DASHBOARD (`http://localhost:8000`):**
> * **Hiển thị Lần Cuối Huấn Luyện (Trained At):** Thể hiện rõ ràng ngày giờ huấn luyện model gần nhất, thuật toán và chỉ số ROC-AUC.
> * **Nút [Trích xuất 15 Đặc trưng]:** Bấm nút để tự động tính toán 15 đặc trưng kỹ thuật & gán nhãn Triple-Barrier từ Parquet.
> * **Nút [Tải Tệp CSV Về Máy]:** Tải trực tiếp file `ml_dataset_train.csv` về máy tính để upload lên Kaggle chỉ với 1 click.
> * **Nút [Tải Lên Model (.joblib)]:** Kéo thả hoặc chọn file `.joblib` đã huấn luyện xong trên Kaggle để cập nhật hệ thống ngay lập tức mà không cần khởi động lại server.
> * **Bảng Xếp Hạng Alpha Toàn Sàn:** Bảng điểm xác suất tăng giá thời gian thực cho từng mã cổ phiếu (HPG, MBB, SSI...).

---

### Quy Trình Huấn Luyện Thủ Công Qua Dòng Lệnh (Nếu Cần):
1. **Trích xuất 15 Đặc trưng Kỹ thuật & Gán nhãn Triple-Barrier:**
   ```bash
   python3 tools/ml_feature_extractor.py --output data/ml_dataset_train.parquet --csv
   ```
2. **Huấn luyện Mô hình trên Kaggle / Google Colab (Miễn phí):**
   * Mở Notebook [`notebooks/kaggle_train_lightgbm.ipynb`](notebooks/kaggle_train_lightgbm.ipynb) trên Kaggle và bấm **Run All**.
   * Tải tệp mô hình `universal_alpha_model.joblib` về và upload lên Dashboard hoặc thả vào thư mục `models/`.
3. **Suy Luận & Chấm Điểm Alpha Score (< 0.005s):**
   ```bash
   python3 tools/ml_predictor.py
   ```
Hoặc trong code chiến lược:
```python
ml_score = self.get_ml_score("HPG")  # Trả về điểm số từ 0.00 đến 1.00
```

---

## 9. KHỞI CHẠY WEB DASHBOARD & DOCKER COMPOSE

### Khởi chạy Dashboard trực tiếp:
```bash
python3 main.py --serve-dashboard
```
Mở trình duyệt truy cập: **`http://localhost:8000`**
* **Nút [Đồng Bộ Giá BigQuery]:** Cập nhật giá đóng cửa thực tế mới nhất từ BigQuery chỉ với 1 click.
* **Bộ Lọc Đa Tài Khoản (Account Pills):** Chuyển đổi linh hoạt giữa Toàn quỹ (`ALL`), Tài khoản hiện hành (`0001716319`), hoặc các tài khoản cũ (`009C105992`, `127008`).
* **Tổng quan Tài sản (Overview Cards):**
  - **NAV:** Tổng tài sản ròng chuẩn hóa Mark-to-Market.
  - **Biến Động Trong Ngày (Daily PnL):** So sánh chuẩn xác giữa phiên $T$ và phiên $T-1$ theo nến BigQuery.
  - **Lợi Nhuận Lũy Kế:** Bóc tách minh bạch Lãi đã chốt tiền mặt (Realized) và Lãi/lỗ tạm tính (Unrealized) kèm ghi chú FLC treo sàn.
* **Danh mục Nắm giữ:** Tỷ trọng từng mã, giá vốn bình quân (2 chữ số thập phân), thị giá thực tế và badge nhận diện cổ phiếu ngừng giao dịch.
* **Đường Cong Vốn Thực Tế (Equity Curve):** 4 thẻ số liệu vốn kế toán chuẩn mực (Vốn gốc đang gửi, NAV, Lợi nhuận toàn lịch sử, Tỷ suất sinh lời thực tế) — loại bỏ hoàn toàn con số giả định.
* **Phòng Thí Nghiệm Machine Learning:** Xem ngày giờ huấn luyện, trích xuất 15 đặc trưng, tải dataset CSV về máy và tải lên file model `.joblib` huấn luyện từ Kaggle.
* **Sổ Lệnh Điện Tử & Form Nhập Lệnh Khớp:** Ghi nhận lệnh bù tức thì vào sổ cái kế toán.

---

## 10. HỆ THỐNG KẾ TOÁN QUỸ & QUẢN TRỊ ĐA TÀI KHOẢN (HISTORICAL VAULT)

Hệ thống quản lý nguồn vốn thực tế thông qua việc tái hiện (Replay) **1.710 giao dịch lịch sử từ 16/06/2016 đến nay** qua 4 tài khoản CTCK (`0001716319`, `009C105992`, `127008`, `123C006116`), độc lập hóa 100% bằng code toán học chuẩn xác:

### 1. Công thức Kế toán Chuẩn mực:
* **Giá vốn bình quân (`Avg Price`):**
  * *Khi Mua:* Gộp phí mua vào giá vốn:
    $$\text{Avg Price}_{mới} = \frac{(Q_{cũ} \times \text{Avg Price}_{cũ}) + (Q_{mua} \times P_{mua}) + \text{Phí}_{mua}}{Q_{cũ} + Q_{mua}}$$
  * *Khi nhận Cổ tức Tiền mặt:* Khấu trừ trực tiếp vào giá vốn:
    $$\text{Avg Price}_{mới} = \frac{(Q_{cũ} \times \text{Avg Price}_{cũ}) - \text{Tổng tiền cổ tức}}{Q_{cũ}}$$
  * *Khi nhận Cổ tức Cổ phiếu / Cổ phiếu thưởng:* Pha loãng giá vốn. Đặc biệt từ **05/12/2020** (Nghị định 126/2020/NĐ-CP), tính thêm thuế TNCN 5% trên mệnh giá 10.000 đ/CP:
    $$\text{Avg Price}_{mới} = \frac{(Q_{cũ} \times \text{Avg Price}_{cũ}) + (Q_{thưởng} \times 10.000 \times 5\%)}{Q_{cũ} + Q_{thưởng}}$$
* **Lãi/Lỗ Thực Hiện (`Profit` & `Profit Percent`):**
  $$\text{Profit} = \text{Tổng tiền thực nhận (đã trừ phí, thuế)} - (|Q_{bán}| \times \text{Avg Price}_{cũ})$$
  $$\text{Profit Percent} = \frac{\text{Profit}}{|Q_{bán}| \times \text{Avg Price}_{cũ}}$$

### 2. Quy Tắc Thận Trọng Cho Cổ Phiếu Treo Sàn (Suspended Stocks):
* Đối với các mã bị đình chỉ giao dịch / hủy niêm yết (như **FLC**: 12.700 CP ở TK `009C105992` và 12.700 CP ở TK `127008`):
  * Hệ thống tự động định giá thị giá = **`0,00 đ`** (0% tỷ trọng trong NAV).
  * Giúp bảo toàn tính thanh khoản và sự chính xác của NAV thật (`217.026.062 đ` thay vì bị thổi phồng ảo lên 382 triệu).

### 3. Mô Hình Vốn Gốc Quản Trị Chuẩn & Nguyên Lý Vốn Gốc Không Âm:
* **Nguyên tắc thu hồi vốn gốc (Return of Capital):** Khi rút tiền, số tiền rút sẽ trừ dần vào vốn gốc đã nộp cho đến khi vốn gốc về `0 đ`.
* **Rút lợi nhuận (Profit Distribution):** Khi vốn gốc đã về `0 đ`, nếu rút tiếp thì khoản tiền đó được ghi nhận chuẩn xác là **Tiền lãi đã rút về ngân hàng** (`profit_withdrawn`), vốn gốc **KHÔNG BAO GIỜ BỊ ÂM**.
* **Tái tạo chu kỳ vốn mới:** Khi nộp thêm tiền sau đó, số tiền nộp mới sẽ khởi tạo lại chu kỳ vốn gốc mới.
* **Bảng tổng hợp nguồn vốn qua 1.710 giao dịch:**
  * **Tổng nộp vào:** `1.584.347.696 đ` (qua 59 lần nộp)
  * **Tổng rút ra:** `1.399.046.954 đ` (qua 40 lần rút)
  * **Vốn gốc đang đầu tư (Active Capital):** **`252.273.370 đ`** (`0001716319`: 100.77M, `127008`: 151.5M, `009C105992`: 0đ, `123C006116`: 0đ).
  * **Tiền lãi đã rút về ngân hàng (Profit Withdrawn):** **`+66.972.628 đ`** (`009C105992`: 65.66M, `123C006116`: 1.31M).
  * **Tổng lợi nhuận thực nhận toàn bộ lịch sử:**
    $$\text{Net Profit} = (\text{NAV} - \text{Active Capital}) + \text{Profit Withdrawn} = \mathbf{+31.725.320 \text{ đ}}$$

### 4. Lệnh Nạp / Tái Hiện Kế Toán:
```bash
python3 tools/transaction_importer.py
```
* **Kết quả tài khoản hiện hành (`0001716319`):** Tiền mặt: **326.812 VND**; Cổ phiếu: **FPT** (1.560 CP), **HPG** (2.000 CP), **MBS** (3.000 CP), **SHS** (3.000 CP), **SSI** (405 CP).
* **Các tài khoản cũ:** Số dư tiền mặt đã cân bằng chuẩn xác về **0 VND**.

---

## 11. BỘ KIỂM THỬ HỆ THỐNG (TEST SUITES)

Dự án đi kèm 6 bộ kiểm thử tự động toàn diện. Chạy toàn bộ test chỉ với 1 câu lệnh:

```bash
python3 tests/test_historical_accounting.py && \
python3 tests/test_phase1.py && \
python3 tests/test_phase2.py && \
python3 tests/test_phase3.py && \
python3 tests/test_evolution.py && \
python3 tests/test_ml_pipeline.py
```

| Bộ Kiểm Thử | Tệp Kiểm Thử | Nội Dung Xác Minh |
| :--- | :--- | :--- |
| **Kế toán Quỹ** | [`tests/test_historical_accounting.py`](tests/test_historical_accounting.py) | Replay 1.710 GD, số dư tiền mặt 4 tài khoản, danh mục thực tế (FPT, HPG, MBS, SHS, SSI), cổ tức tiền/cổ phiếu NĐ 126. |
| **Giai đoạn 1** | [`tests/test_phase1.py`](tests/test_phase1.py) | CSDL SQLite, nạp dữ liệu Parquet, khớp lệnh mua/bán, tính thuế phí và chốt sổ NAV Mark-to-Market. |
| **Giai đoạn 2** | [`tests/test_phase2.py`](tests/test_phase2.py) | Động cơ `vn-backtest`, quy tắc $T+2.5$, lô chẵn 100, tạo Skill và xuất biểu đồ Plotly HTML. |
| **Giai đoạn 3** | [`tests/test_phase3.py`](tests/test_phase3.py) | Định dạng tin nhắn Telegram 2 chiều Bull/Bear, bóc tách regex `/fill`, và các REST API của Dashboard. |
| **Tiến hóa AI** | [`tests/test_evolution.py`](tests/test_evolution.py) | Chẩn đoán nguyên nhân thất bại, tối ưu hóa tham số `ParameterOptimizer`, cập nhật báo cáo và viết Post-Mortem Memo. |
| **Machine Learning**| [`tests/test_ml_pipeline.py`](tests/test_ml_pipeline.py) | Trích xuất 15 đặc trưng, gán nhãn 3 rào cản, huấn luyện LightGBM, dự báo <0.005s và API xếp hạng Alpha. |

---

🏛️ **Hệ thống Quỹ Đầu tư AI sẵn sàng vận hành an toàn, minh bạch và hoàn toàn tự chủ!**

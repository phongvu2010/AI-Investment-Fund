"""
Module Quản trị Cơ sở Dữ liệu Quỹ (Database Manager).
Thực thi các nghiệp vụ Kế toán Quỹ Đa Tài khoản, Sổ lệnh, Danh mục, Cổ tức và Chốt NAV chuẩn xác.
"""

import sqlite3
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from config import settings

class DatabaseManager:
    """Quản trị viên Cơ sở Dữ liệu SQLite fund_vault.db"""

    def __init__(self, db_path: Optional[Any] = None):
        self.db_path = Path(db_path) if db_path else settings.SQLITE_DB_PATH
        self.schema_path = settings.DATABASE_DIR / "schema.sql"
        self._ensure_db()
        self.migrate_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Tạo kết nối SQLite có hỗ trợ row dictionary và bật foreign keys"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _ensure_db(self):
        """Khởi tạo cấu trúc bảng từ schema.sql nếu database chưa tồn tại"""
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            self.init_db()

    def migrate_schema(self):
        """Tự động kiểm tra và nâng cấp schema an toàn (ALTER TABLE) nếu các cột mới chưa tồn tại"""
        with self.get_connection() as conn:
            # 1. Bảng portfolio: kiểm tra cột strategy_book
            cursor = conn.execute("PRAGMA table_info(portfolio);")
            pf_cols = [r["name"] for r in cursor.fetchall()]
            if "strategy_book" not in pf_cols and len(pf_cols) > 0:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS portfolio_migrated (
                        account TEXT NOT NULL,
                        ticker TEXT NOT NULL,
                        strategy_book TEXT NOT NULL DEFAULT 'QUANT' CHECK(strategy_book IN ('CORE', 'QUANT')),
                        quantity REAL NOT NULL CHECK (quantity >= 0),
                        avg_buy_price REAL NOT NULL,
                        current_price REAL DEFAULT 0.0,
                        market_value REAL DEFAULT 0.0,
                        unrealized_pnl REAL DEFAULT 0.0,
                        unrealized_pnl_pct REAL DEFAULT 0.0,
                        weight_pct REAL DEFAULT 0.0,
                        first_bought_date TEXT,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (account, ticker, strategy_book)
                    );
                """)
                conn.execute("""
                    INSERT INTO portfolio_migrated (
                        account, ticker, strategy_book, quantity, avg_buy_price, current_price,
                        market_value, unrealized_pnl, unrealized_pnl_pct, weight_pct, first_bought_date, updated_at
                    )
                    SELECT account, ticker, 'QUANT', quantity, avg_buy_price, current_price,
                           market_value, unrealized_pnl, unrealized_pnl_pct, weight_pct, first_bought_date, updated_at
                    FROM portfolio;
                """)
                conn.execute("DROP TABLE portfolio;")
                conn.execute("ALTER TABLE portfolio_migrated RENAME TO portfolio;")

            # 2. Bảng order_history: kiểm tra cột strategy_book
            cursor = conn.execute("PRAGMA table_info(order_history);")
            ord_cols = [r["name"] for r in cursor.fetchall()]
            if "strategy_book" not in ord_cols and len(ord_cols) > 0:
                conn.execute("ALTER TABLE order_history ADD COLUMN strategy_book TEXT NOT NULL DEFAULT 'QUANT';")

            # 3. Bảng nav_daily: kiểm tra cột core_nav, quant_nav, liquid_nav, frozen_assets_value, provision_loss
            cursor = conn.execute("PRAGMA table_info(nav_daily);")
            nav_cols = [r["name"] for r in cursor.fetchall()]
            if "core_nav" not in nav_cols and len(nav_cols) > 0:
                conn.execute("ALTER TABLE nav_daily ADD COLUMN core_nav REAL DEFAULT 0.0;")
            if "quant_nav" not in nav_cols and len(nav_cols) > 0:
                conn.execute("ALTER TABLE nav_daily ADD COLUMN quant_nav REAL DEFAULT 0.0;")
                conn.execute("UPDATE nav_daily SET quant_nav = total_nav, core_nav = 0.0 WHERE quant_nav = 0.0 OR quant_nav IS NULL;")
            if "liquid_nav" not in nav_cols and len(nav_cols) > 0:
                conn.execute("ALTER TABLE nav_daily ADD COLUMN liquid_nav REAL DEFAULT 0.0;")
                conn.execute("UPDATE nav_daily SET liquid_nav = total_nav WHERE liquid_nav = 0.0 OR liquid_nav IS NULL;")
            if "frozen_assets_value" not in nav_cols and len(nav_cols) > 0:
                conn.execute("ALTER TABLE nav_daily ADD COLUMN frozen_assets_value REAL DEFAULT 0.0;")
            if "provision_loss" not in nav_cols and len(nav_cols) > 0:
                conn.execute("ALTER TABLE nav_daily ADD COLUMN provision_loss REAL DEFAULT 0.0;")

            # 4. Bảng decision_memos: kiểm tra các cột
            cursor = conn.execute("PRAGMA table_info(decision_memos);")
            memo_cols = [r["name"] for r in cursor.fetchall()]
            if len(memo_cols) > 0:
                if "strategy_book" not in memo_cols:
                    conn.execute("ALTER TABLE decision_memos ADD COLUMN strategy_book TEXT NOT NULL DEFAULT 'QUANT';")
                if "macro_view" not in memo_cols:
                    conn.execute("ALTER TABLE decision_memos ADD COLUMN macro_view TEXT;")
                if "fa_summary" not in memo_cols:
                    conn.execute("ALTER TABLE decision_memos ADD COLUMN fa_summary TEXT;")
                if "ta_ml_summary" not in memo_cols:
                    conn.execute("ALTER TABLE decision_memos ADD COLUMN ta_ml_summary TEXT;")
                if "bull_arguments" not in memo_cols:
                    conn.execute("ALTER TABLE decision_memos ADD COLUMN bull_arguments TEXT;")
                if "bear_arguments" not in memo_cols:
                    conn.execute("ALTER TABLE decision_memos ADD COLUMN bear_arguments TEXT;")
                if "cro_verdict" not in memo_cols:
                    conn.execute("ALTER TABLE decision_memos ADD COLUMN cro_verdict TEXT;")
                if "cro_position_size" not in memo_cols:
                    conn.execute("ALTER TABLE decision_memos ADD COLUMN cro_position_size REAL DEFAULT 0.0;")
                if "cio_decision" not in memo_cols:
                    conn.execute("ALTER TABLE decision_memos ADD COLUMN cio_decision TEXT;")
                if "status" not in memo_cols:
                    conn.execute("ALTER TABLE decision_memos ADD COLUMN status TEXT DEFAULT 'PROPOSED';")
                if "jev_telemetry" not in memo_cols:
                    conn.execute("ALTER TABLE decision_memos ADD COLUMN jev_telemetry TEXT;")

            # 5. Bảng company_fundamentals: tạo nếu chưa tồn tại
            conn.execute("""
                CREATE TABLE IF NOT EXISTS company_fundamentals (
                    ticker TEXT NOT NULL,
                    period TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    quarter INTEGER NOT NULL,
                    revenue_growth_yoy REAL DEFAULT 0.0,
                    profit_growth_yoy REAL DEFAULT 0.0,
                    roe REAL DEFAULT 0.0,
                    gross_margin REAL DEFAULT 0.0,
                    debt_to_equity REAL DEFAULT 0.0,
                    ocf_to_net_income REAL DEFAULT 1.0,
                    pe REAL DEFAULT 15.0,
                    pb REAL DEFAULT 1.5,
                    pe_5y_median REAL DEFAULT 15.0,
                    piotroski_f_score INTEGER DEFAULT 6,
                    altman_z_score REAL DEFAULT 2.6,
                    notes TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (ticker, period)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fund_ticker ON company_fundamentals(ticker);")

            # 6. Bảng suspended_assets: tạo bảng quản lý tài sản đóng băng / đình chỉ / hủy niêm yết
            conn.execute("""
                CREATE TABLE IF NOT EXISTS suspended_assets (
                    ticker TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'SUSPENDED' CHECK(status IN ('SUSPENDED', 'DELISTED', 'FROZEN', 'ACTIVE')),
                    reason TEXT NOT NULL,
                    suspended_date TEXT,
                    provision_rate REAL DEFAULT 1.0 CHECK(provision_rate >= 0.0 AND provision_rate <= 1.0),
                    recovery_estimated_price REAL DEFAULT 0.0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Seed mặc định cho mã FLC (Hủy niêm yết lịch sử)
            conn.execute("""
                INSERT OR IGNORE INTO suspended_assets (ticker, status, reason, suspended_date, provision_rate, recovery_estimated_price, notes)
                VALUES ('FLC', 'DELISTED', 'Hủy niêm yết bắt buộc do vi phạm nghiêm trọng công bố thông tin (QĐ 20/02/2023)', '2023-02-20', 1.0, 0.0, 'Tài sản kẹt sàn lịch sử - Đã trích lập dự phòng 100%');
            """)

            conn.commit()

    def init_db(self, initial_capital: float = settings.INITIAL_CAPITAL) -> bool:
        """Khởi tạo database hoàn toàn mới và nạp vốn ban đầu"""
        with self.get_connection() as conn:
            with open(self.schema_path, "r", encoding="utf-8") as f:
                conn.executescript(f.read())

            # Thiết lập cài đặt hệ thống ban đầu
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            today_str = date.today().strftime("%Y-%m-%d")

            conn.execute("""
                INSERT OR REPLACE INTO system_settings (key, value, description, updated_at)
                VALUES 
                    ('active_account', '0001716319', 'Tài khoản giao dịch chính đang kích hoạt', ?),
                    ('initial_capital', ?, 'Vốn khởi lập của Quỹ (VND)', ?),
                    ('fund_status', 'ACTIVE', 'Trạng thái hoạt động của Quỹ', ?),
                    ('base_currency', 'VND', 'Đơn vị tiền tệ cơ sở', ?),
                    ('last_bigquery_sync', '', 'Thời điểm đồng bộ BigQuery gần nhất', ?);
            """, (now_str, str(initial_capital), now_str, now_str, now_str, now_str))

            # Khởi tạo các tài khoản CTCK mặc định
            conn.execute("""
                INSERT OR IGNORE INTO broker_accounts (account_id, broker_name, fee_rate, status, opened_date, notes)
                VALUES 
                    ('0001716319', 'VNDIRECT / TCBS', 0.00097, 'ACTIVE', '2023-09-06', 'Tài khoản giao dịch chính hiện tại'),
                    ('009C105992', 'VCBS', 0.0015, 'INACTIVE', '2016-06-16', 'Tài khoản VCBS giai đoạn 2016-2024'),
                    ('127008', 'VPS', 0.001, 'INACTIVE', '2021-04-29', 'Tài khoản VPS giai đoạn 2021-2023'),
                    ('123C006116', 'DNSE / KAFI', 0.001, 'CLOSED', '2025-02-05', 'Tài khoản phụ đã tất toán');
            """)

            # Thiết lập số dư tiền mặt khởi điểm
            conn.execute("""
                INSERT OR REPLACE INTO account_cash_balance (account_id, cash_balance, updated_at)
                VALUES 
                    ('0001716319', ?, CURRENT_TIMESTAMP),
                    ('009C105992', 0.0, CURRENT_TIMESTAMP),
                    ('127008', 0.0, CURRENT_TIMESTAMP),
                    ('123C006116', 0.0, CURRENT_TIMESTAMP);
            """, (initial_capital,))

            # Khởi tạo bản ghi NAV ngày 0 nếu chưa có
            cursor = conn.execute("SELECT COUNT(*) FROM nav_daily;")
            if cursor.fetchone()[0] == 0:
                conn.execute("""
                    INSERT INTO nav_daily (
                        trade_date, total_nav, cash_balance, stock_value, 
                        daily_pnl, daily_pnl_pct, cumulative_pnl, realized_pnl, unrealized_pnl,
                        nav_per_share, notes
                    ) VALUES (?, ?, ?, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 10000.0, 'Khởi lập Quỹ Đầu tư');
                """, (today_str, initial_capital, initial_capital))

            conn.commit()
        return True

    # ==========================================
    # TIỀN MẶT & DANH MỤC (PORTFOLIO & CASH)
    # ==========================================
    def get_current_cash(self, account: Optional[str] = None) -> float:
        """Lấy số dư tiền mặt hiện tại (theo tài khoản hoặc tổng hợp)"""
        with self.get_connection() as conn:
            if account and account != "ALL":
                row = conn.execute("SELECT cash_balance FROM account_cash_balance WHERE account_id = ?;", (account,)).fetchone()
                if row:
                    return float(row["cash_balance"])
            else:
                row = conn.execute("SELECT SUM(cash_balance) as total_cash FROM account_cash_balance;").fetchone()
                if row and row["total_cash"] is not None:
                    return float(row["total_cash"])

            # Fallback lấy từ nav_daily gần nhất
            row_nav = conn.execute("""
                SELECT cash_balance FROM nav_daily 
                ORDER BY trade_date DESC, created_at DESC LIMIT 1;
            """).fetchone()
            if row_nav:
                return float(row_nav["cash_balance"])
            return settings.INITIAL_CAPITAL

    def calculate_available_shares(
        self,
        ticker: str,
        account: str = "0001716319",
        strategy_book: Optional[str] = None,
        as_of_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Tính toán số lượng cổ phiếu khả dụng để bán theo đúng quy chế T+2.5 của sàn Việt Nam (VSD).
        - Ngày T mua: T+0 (chưa về).
        - Ngày T+1: T+1 (chưa về).
        - Ngày T+2: Cổ phiếu về chiều T+2 (sau 13:00) / sẵn sàng giao dịch (trading_days >= 2).
        - Cuối tuần (thứ 7, CN) không tính là ngày giao dịch.
        """
        t = ticker.upper()
        as_of_str = as_of_date or date.today().strftime("%Y-%m-%d")
        try:
            as_of_dt = datetime.strptime(as_of_str, "%Y-%m-%d").date()
        except Exception:
            as_of_dt = date.today()

        with self.get_connection() as conn:
            pf_query = "SELECT quantity, first_bought_date FROM portfolio WHERE account = ? AND ticker = ?"
            pf_params = [account, t]
            if strategy_book and strategy_book != "ALL":
                pf_query += " AND strategy_book = ?"
                pf_params.append(strategy_book.upper())
            pf_rows = conn.execute(pf_query, tuple(pf_params)).fetchall()
            current_portfolio_qty = sum(float(r["quantity"]) for r in pf_rows)

            if current_portfolio_qty <= 0:
                return {
                    "ticker": t,
                    "account": account,
                    "strategy_book": strategy_book,
                    "total_quantity": 0.0,
                    "available_quantity": 0.0,
                    "pending_settlement_quantity": 0.0,
                    "settled_lots": [],
                    "pending_lots": []
                }

            tx_rows = conn.execute("""
                SELECT trade_date, type, quantity, comment
                FROM transactions
                WHERE account = ? AND symbol = ? AND trade_date <= ?
                ORDER BY trade_date ASC, id ASC;
            """, (account, t, as_of_str)).fetchall()

            lots = []
            for tx in tx_rows:
                tx_type = str(tx["type"]).upper()
                q = float(tx["quantity"])
                t_date = str(tx["trade_date"])
                
                if q > 0 or "MUA" in tx_type or "BUY" in tx_type:
                    buy_qty = abs(q)
                    lots.append({"date": t_date, "qty": buy_qty})
                elif q < 0 or "BÁN" in tx_type or "SELL" in tx_type:
                    sell_qty = abs(q)
                    while sell_qty > 0 and lots:
                        if lots[0]["qty"] <= sell_qty:
                            sell_qty -= lots[0]["qty"]
                            lots.pop(0)
                        else:
                            lots[0]["qty"] -= sell_qty
                            sell_qty = 0

            if not lots and current_portfolio_qty > 0:
                first_date = pf_rows[0]["first_bought_date"] or as_of_str
                lots.append({"date": first_date, "qty": current_portfolio_qty})

            settled_lots = []
            pending_lots = []
            available_qty = 0.0
            pending_qty = 0.0

            for lot in lots:
                try:
                    lot_dt = datetime.strptime(lot["date"], "%Y-%m-%d").date()
                except Exception:
                    lot_dt = as_of_dt

                trading_days = 0
                curr = lot_dt + timedelta(days=1)
                while curr <= as_of_dt:
                    if curr.weekday() < 5:
                        trading_days += 1
                    curr += timedelta(days=1)

                lot_info = {
                    "buy_date": lot["date"],
                    "quantity": lot["qty"],
                    "trading_days": trading_days,
                    "status": "SETTLED" if trading_days >= 2 else f"T+{trading_days}"
                }

                if trading_days >= 2:
                    available_qty += lot["qty"]
                    settled_lots.append(lot_info)
                else:
                    pending_qty += lot["qty"]
                    pending_lots.append(lot_info)

            total_sum = available_qty + pending_qty
            if total_sum > 0 and total_sum != current_portfolio_qty:
                scale = current_portfolio_qty / total_sum
                available_qty = round(available_qty * scale)
                pending_qty = current_portfolio_qty - available_qty

            return {
                "ticker": t,
                "account": account,
                "strategy_book": strategy_book,
                "total_quantity": current_portfolio_qty,
                "available_quantity": available_qty,
                "pending_settlement_quantity": pending_qty,
                "settled_lots": settled_lots,
                "pending_lots": pending_lots
            }

    def get_portfolio(self, account: Optional[str] = None, strategy_book: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lấy danh mục cổ phiếu đang nắm giữ (hỗ trợ lọc theo tài khoản, sổ chiến lược CORE/QUANT và tính khả dụng T+2.5)"""
        with self.get_connection() as conn:
            query = """
                SELECT account, ticker, strategy_book, quantity, avg_buy_price, current_price, market_value,
                       unrealized_pnl, unrealized_pnl_pct, weight_pct, first_bought_date, updated_at
                FROM portfolio 
                WHERE quantity > 0
            """
            params = []
            if account and account != "ALL":
                query += " AND account = ?"
                params.append(account)
            if strategy_book and strategy_book != "ALL":
                query += " AND strategy_book = ?"
                params.append(strategy_book.upper())

            if account and account != "ALL":
                query += " ORDER BY market_value DESC;"
            else:
                query += " ORDER BY (account = '0001716319') DESC, market_value DESC;"

            rows = conn.execute(query, tuple(params)).fetchall()
            # Lấy danh sách tài sản đóng băng
            susp_map = {r["ticker"].upper(): r for r in self.get_suspended_assets()}

            results = []
            for row in rows:
                item = dict(row)
                t_up = item["ticker"].upper()
                is_susp = t_up in susp_map and susp_map[t_up]["status"] != "ACTIVE"
                susp_info = susp_map.get(t_up, {})

                item["asset_status"] = susp_info.get("status", "ACTIVE") if is_susp else "ACTIVE"
                item["is_liquid"] = not is_susp
                item["provision_rate"] = susp_info.get("provision_rate", 0.0) if is_susp else 0.0
                item["suspension_reason"] = susp_info.get("reason", "") if is_susp else ""

                avail_info = self.calculate_available_shares(
                    ticker=item["ticker"],
                    account=item["account"],
                    strategy_book=item["strategy_book"]
                )
                item["available_quantity"] = 0.0 if is_susp else avail_info.get("available_quantity", item["quantity"])
                item["pending_settlement_quantity"] = avail_info.get("pending_settlement_quantity", 0)
                results.append(item)
            return results

    # ==========================================
    # QUẢN TRỊ TÀI SẢN ĐÓNG BĂNG (SUSPENDED / FROZEN ASSETS)
    # ==========================================
    def get_suspended_assets(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các cổ phiếu bị đình chỉ, hủy niêm yết hoặc đóng băng tài sản"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT ticker, status, reason, suspended_date, provision_rate, 
                       recovery_estimated_price, notes, created_at, updated_at
                FROM suspended_assets
                ORDER BY ticker ASC;
            """).fetchall()
            return [dict(row) for row in rows]

    def set_asset_suspension(
        self,
        ticker: str,
        status: str = "SUSPENDED",
        reason: str = "Đình chỉ giao dịch / Hủy niêm yết",
        suspended_date: Optional[str] = None,
        provision_rate: float = 1.0,
        recovery_estimated_price: float = 0.0,
        notes: Optional[str] = None
    ) -> bool:
        """Thiết lập trạng thái đình chỉ / đóng băng hoặc cập nhật tỷ lệ trích lập dự phòng cho cổ phiếu"""
        t = ticker.upper()
        s_date = suspended_date or date.today().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO suspended_assets (
                    ticker, status, reason, suspended_date, provision_rate,
                    recovery_estimated_price, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (t, status.upper(), reason, s_date, min(max(provision_rate, 0.0), 1.0), recovery_estimated_price, notes, now_str))
            conn.commit()
        return True

    def remove_asset_suspension(self, ticker: str) -> bool:
        """Gỡ bỏ trạng thái đình chỉ (chuyển sang ACTIVE hoặc xóa khỏi danh sách đóng băng)"""
        t = ticker.upper()
        with self.get_connection() as conn:
            conn.execute("DELETE FROM suspended_assets WHERE ticker = ?;", (t,))
            conn.commit()
        return True

    def is_asset_suspended(self, ticker: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Kiểm tra nhanh xem một mã cổ phiếu có đang bị đình chỉ / đóng băng hay không"""
        t = ticker.upper()
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT ticker, status, reason, suspended_date, provision_rate, recovery_estimated_price, notes
                FROM suspended_assets
                WHERE ticker = ? AND status != 'ACTIVE';
            """, (t,)).fetchone()
            if row:
                return True, dict(row)
            return False, None


    def get_broker_accounts(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các tài khoản chứng khoán và số dư tiền mặt"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT b.account_id, b.broker_name, b.fee_rate, b.status, b.opened_date, b.notes,
                       COALESCE(c.cash_balance, 0.0) as cash_balance
                FROM broker_accounts b
                LEFT JOIN account_cash_balance c ON b.account_id = c.account_id
                ORDER BY (b.status = 'ACTIVE') DESC, b.account_id ASC;
            """).fetchall()
            return [dict(row) for row in rows]


    def get_recent_transactions(self, account: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Lấy lịch sử giao dịch gần nhất"""
        with self.get_connection() as conn:
            if account:
                rows = conn.execute("""
                    SELECT * FROM transactions 
                    WHERE account = ?
                    ORDER BY trade_date DESC, id DESC LIMIT ?;
                """, (account, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM transactions 
                    ORDER BY trade_date DESC, id DESC LIMIT ?;
                """, (limit,)).fetchall()
            return [dict(row) for row in rows]


    # ==========================================
    # QUẢN LÝ SỔ LỆNH (ORDERS & RECONCILIATION)
    # ==========================================
    def create_proposed_order(
        self,
        ticker: str,
        action: str,
        proposed_price: float,
        proposed_volume: int,
        order_type: str = "LO",
        memo_id: Optional[str] = None,
        notes: Optional[str] = None,
        trade_date: Optional[str] = None,
        account: str = "0001716319",
        strategy_book: str = "QUANT"
    ) -> str:
        """AI tạo lệnh đề xuất gửi Telegram cho Bạn (có kiểm tra quy chế khả dụng T+2.5 khi BÁN)"""
        norm_proposed_price = proposed_price * 1000.0 if proposed_price < 1000.0 else proposed_price
        t_date = trade_date or date.today().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{ticker}"

        # Kiểm tra kiểm soát T+2.5 khi ra lệnh BÁN
        if action.upper() == "SELL":
            avail_info = self.calculate_available_shares(
                ticker=ticker.upper(), account=account, strategy_book=strategy_book.upper(), as_of_date=t_date
            )
            avail_qty = avail_info.get("available_quantity", 0)
            if proposed_volume > avail_qty:
                raise ValueError(
                    f"CRO VETO [T+2.5 SETTLEMENT]: Không thể tạo lệnh BÁN {proposed_volume:,} CP {ticker.upper()}. "
                    f"Số lượng khả dụng giao dịch chỉ có: {avail_qty:,} CP. "
                    f"Số lượng đang chờ về T+2.5: {avail_info.get('pending_settlement_quantity', 0):,} CP."
                )

        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO order_history (
                    order_id, account, ticker, strategy_book, action, order_type, proposed_price, proposed_volume,
                    status, trade_date, memo_id, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PROPOSED', ?, ?, ?, ?);
            """, (order_id, account, ticker.upper(), strategy_book.upper(), action.upper(), order_type, norm_proposed_price, proposed_volume, t_date, memo_id, notes, now_str))
            conn.commit()
        return order_id

    def set_order_submitted(self, order_id: str) -> bool:
        """Đánh dấu Bạn đã đặt lệnh trên App CTCK, lệnh đang chờ sàn khớp"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE order_history 
                SET status = 'SUBMITTED' 
                WHERE order_id = ?;
            """, (order_id,))
            conn.commit()
        return True

    def record_order_fill(
        self,
        order_id: str,
        executed_price: float,
        executed_volume: int,
        executed_at: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Xác nhận khớp lệnh thực tế:
        1. Cập nhật trạng thái lệnh (FILLED hoặc PARTIALLY_FILLED)
        2. Tính toán phí CTCK, thuế TNCN (0.1% nếu bán), trượt giá (Slippage)
        3. Cập nhật số dư tiền mặt & danh mục cổ phiếu
        """
        norm_executed_price = executed_price * 1000.0 if executed_price < 1000.0 else executed_price
        now_str = executed_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.get_connection() as conn:
            order = conn.execute("SELECT * FROM order_history WHERE order_id = ?;", (order_id,)).fetchone()
            if not order:
                raise ValueError(f"Không tìm thấy lệnh với ID: {order_id}")

            ticker = order["ticker"]
            action = order["action"]
            proposed_price = order["proposed_price"]
            proposed_volume = order["proposed_volume"]
            account = order["account"] if "account" in order.keys() and order["account"] else "0001716319"
            strategy_book = order["strategy_book"] if "strategy_book" in order.keys() and order["strategy_book"] else "QUANT"

            # Lấy biểu phí tài khoản
            acc_row = conn.execute("SELECT fee_rate FROM broker_accounts WHERE account_id = ?;", (account,)).fetchone()
            fee_rate = float(acc_row["fee_rate"]) if acc_row else settings.BROKER_FEE_RATE

            trade_value = norm_executed_price * executed_volume
            fee = trade_value * fee_rate
            tax = trade_value * settings.SELL_TAX_RATE if action == "SELL" else 0.0

            slippage_pct = ((norm_executed_price - proposed_price) / proposed_price) * 100.0 if proposed_price > 0 else 0.0
            status = "FILLED" if executed_volume >= proposed_volume else "PARTIALLY_FILLED"

            conn.execute("""
                UPDATE order_history
                SET executed_price = ?, executed_volume = ?, status = ?,
                    fee = ?, tax = ?, slippage_pct = ?, executed_at = ?, notes = COALESCE(?, notes)
                WHERE order_id = ?;
            """, (norm_executed_price, executed_volume, status, fee, tax, slippage_pct, now_str, notes, order_id))

            self._apply_trade_to_portfolio_and_cash(
                conn, ticker, action, norm_executed_price, executed_volume, fee, tax, order["trade_date"], account=account, strategy_book=strategy_book
            )
            conn.commit()

        return {
            "order_id": order_id,
            "account": account,
            "ticker": ticker,
            "strategy_book": strategy_book,
            "action": action,
            "executed_price": norm_executed_price,
            "executed_volume": executed_volume,
            "fee": fee,
            "tax": tax,
            "slippage_pct": slippage_pct,
            "status": status
        }

    def record_retroactive_fill(
        self,
        ticker: str,
        action: str,
        executed_price: float,
        executed_volume: int,
        trade_date: Optional[str] = None,
        notes: str = "Nhập bù thủ công qua Telegram",
        account: str = "0001716319",
        strategy_book: str = "QUANT"
    ) -> str:
        """Cơ chế Nhập bù trực tiếp: Nhập bù lệnh khớp từ app CTCK (kiểm tra khả dụng T+2.5 khi BÁN)"""
        norm_executed_price = executed_price * 1000.0 if executed_price < 1000.0 else executed_price
        t_date = trade_date or date.today().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_id = f"FILL-{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{ticker.upper()}"

        if action.upper() == "SELL":
            avail_info = self.calculate_available_shares(
                ticker=ticker.upper(), account=account, strategy_book=strategy_book.upper(), as_of_date=t_date
            )
            avail_qty = avail_info.get("available_quantity", 0)
            if executed_volume > avail_qty:
                raise ValueError(
                    f"CRO VETO [T+2.5 SETTLEMENT]: Không thể khớp lệnh BÁN {executed_volume:,} CP {ticker.upper()}. "
                    f"Số lượng khả dụng giao dịch chỉ có: {avail_qty:,} CP (chờ về T+2.5: {avail_info.get('pending_settlement_quantity', 0):,} CP)."
                )

        with self.get_connection() as conn:
            acc_row = conn.execute("SELECT fee_rate FROM broker_accounts WHERE account_id = ?;", (account,)).fetchone()
            fee_rate = float(acc_row["fee_rate"]) if acc_row else settings.BROKER_FEE_RATE

            trade_value = norm_executed_price * executed_volume
            fee = trade_value * fee_rate
            tax = trade_value * settings.SELL_TAX_RATE if action.upper() == "SELL" else 0.0

            conn.execute("""
                INSERT INTO order_history (
                    order_id, account, ticker, strategy_book, action, order_type, proposed_price, proposed_volume,
                    executed_price, executed_volume, status, fee, tax, slippage_pct,
                    trade_date, created_at, executed_at, notes
                ) VALUES (?, ?, ?, ?, ?, 'LO', ?, ?, ?, ?, 'FILLED', ?, ?, 0.0, ?, ?, ?, ?);
            """, (order_id, account, ticker.upper(), strategy_book.upper(), action.upper(), norm_executed_price, executed_volume,
                  norm_executed_price, executed_volume, fee, tax, t_date, now_str, now_str, notes))

            self._apply_trade_to_portfolio_and_cash(
                conn, ticker.upper(), action.upper(), norm_executed_price, executed_volume, fee, tax, t_date, account=account, strategy_book=strategy_book.upper()
            )
            conn.commit()

        return order_id

    def _apply_trade_to_portfolio_and_cash(
        self,
        conn: sqlite3.Connection,
        ticker: str,
        action: str,
        price: float,
        volume: int,
        fee: float,
        tax: float,
        trade_date: str,
        account: str = "0001716319",
        strategy_book: str = "QUANT"
    ):
        """
        Nghiệp vụ hạch toán biến động cổ phiếu và tiền mặt trong cùng 1 transaction:
        - Mua: Gộp phí mua vào giá vốn Avg Price: ((Q_cũ * Avg_cũ) + (Q_mua * P_mua) + Phí_mua) / (Q_cũ + Q_mua)
        - Bán: Tính chuẩn Realized Profit = Tiền thực nhận - (Q_bán * Avg_cũ); Avg Price giữ nguyên.
        """
        # Lấy số dư tiền mặt của tài khoản
        cash_row = conn.execute("SELECT cash_balance FROM account_cash_balance WHERE account_id = ?;", (account,)).fetchone()
        current_acc_cash = float(cash_row["cash_balance"]) if cash_row else 0.0

        # Lấy vị thế hiện tại của cổ phiếu trong tài khoản này theo đúng Sổ chiến lược
        pf_row = conn.execute(
            "SELECT * FROM portfolio WHERE account = ? AND ticker = ? AND strategy_book = ?;", 
            (account, ticker, strategy_book)
        ).fetchone()

        calc_avg_price = None
        calc_profit = None
        calc_profit_pct = None
        tot_amount = 0.0

        if action.upper() == "BUY":
            # TIỀN MẶT GIẢM = (Giá * Khối lượng) + Phí
            cash_outflow = (price * volume) + fee
            new_acc_cash = current_acc_cash - cash_outflow
            tot_amount = -cash_outflow

            if pf_row:
                old_qty = float(pf_row["quantity"])
                old_avg_price = float(pf_row["avg_buy_price"])
                new_qty = old_qty + volume
                # CÔNG THỨC CHUẨN: Gộp phí mua vào giá vốn bình quân gia quyền
                new_avg_price = ((old_qty * old_avg_price) + (volume * price) + fee) / new_qty
                market_val = new_qty * price
                calc_avg_price = new_avg_price

                conn.execute("""
                    UPDATE portfolio
                    SET quantity = ?, avg_buy_price = ?, current_price = ?, market_value = ?,
                        unrealized_pnl = ?, unrealized_pnl_pct = 0.0, updated_at = CURRENT_TIMESTAMP
                    WHERE account = ? AND ticker = ? AND strategy_book = ?;
                """, (new_qty, new_avg_price, price, market_val, market_val - (new_qty * new_avg_price), account, ticker, strategy_book))
            else:
                new_avg_price = ((volume * price) + fee) / volume if volume > 0 else price
                market_val = volume * price
                calc_avg_price = new_avg_price

                conn.execute("""
                    INSERT INTO portfolio (
                        account, ticker, strategy_book, quantity, avg_buy_price, current_price, market_value,
                        unrealized_pnl, unrealized_pnl_pct, first_bought_date, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, ?, CURRENT_TIMESTAMP);
                """, (account, ticker, strategy_book, volume, new_avg_price, price, market_val, trade_date))

        elif action.upper() == "SELL":
            # TIỀN MẶT TĂNG = (Giá * Khối lượng) - (Phí + Thuế)
            cash_inflow = (price * volume) - (fee + tax)
            new_acc_cash = current_acc_cash + cash_inflow
            tot_amount = cash_inflow

            if pf_row:
                old_qty = float(pf_row["quantity"])
                old_avg_price = float(pf_row["avg_buy_price"])
                cost_sold = volume * old_avg_price

                calc_profit = cash_inflow - cost_sold
                calc_profit_pct = calc_profit / cost_sold if cost_sold > 0 else 0.0
                calc_avg_price = old_avg_price

                new_qty = max(0.0, old_qty - volume)
                if new_qty < 1e-4:
                    conn.execute("DELETE FROM portfolio WHERE account = ? AND ticker = ? AND strategy_book = ?;", (account, ticker, strategy_book))
                else:
                    market_val = new_qty * price
                    conn.execute("""
                        UPDATE portfolio
                        SET quantity = ?, current_price = ?, market_value = ?,
                            unrealized_pnl = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE account = ? AND ticker = ? AND strategy_book = ?;
                    """, (new_qty, price, market_val, market_val - (new_qty * old_avg_price), account, ticker, strategy_book))

        # Cập nhật số dư tiền mặt tài khoản
        conn.execute("""
            INSERT OR REPLACE INTO account_cash_balance (account_id, cash_balance, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP);
        """, (account, new_acc_cash))

        # Lưu bản ghi vĩnh viễn vào sổ giao dịch transactions
        trans_type = "Mua" if action.upper() == "BUY" else "Bán"
        signed_qty = volume if action.upper() == "BUY" else -volume
        conn.execute("""
            INSERT INTO transactions (
                trade_date, account, type, symbol, quantity, cost, fee, tax,
                amount, total_amount, avg_price, profit, profit_pct, comment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (trade_date, account, trans_type, ticker, signed_qty, price, fee, tax,
              price * volume, tot_amount, calc_avg_price, calc_profit, calc_profit_pct, f"[{strategy_book}] Khớp lệnh {action} {ticker}"))

    def apply_corporate_action(
        self,
        ticker: str,
        action_type: str,
        ratio: float = 0.0,
        cash_amount: float = 0.0,
        ex_date: Optional[str] = None,
        account: str = "0001716319"
    ) -> Dict[str, Any]:
        """
        Xử lý sự kiện quyền doanh nghiệp:
        - Cổ tức tiền mặt: Avg Price mới = (Avg Price cũ * Q cũ - Tiền cổ tức) / Q cũ
        - Cổ tức cổ phiếu: Avg Price mới = (Avg Price cũ * Q cũ + Thuế 5%) / (Q cũ + Q thưởng)
          (với Thuế 5% = Q thưởng * 10.000 * 5% nếu ngày GDKHQ >= 05/12/2020)
        """
        ex_d = ex_date or date.today().strftime("%Y-%m-%d")
        ex_dt = pd.to_datetime(ex_d)
        tax_cutoff = pd.to_datetime("2020-12-05")

        with self.get_connection() as conn:
            pf_row = conn.execute("SELECT * FROM portfolio WHERE account = ? AND ticker = ?;", (account, ticker)).fetchone()
            if not pf_row or float(pf_row["quantity"]) <= 0:
                raise ValueError(f"Tài khoản {account} không nắm giữ cổ phiếu {ticker} để nhận cổ tức!")

            old_qty = float(pf_row["quantity"])
            old_avg_price = float(pf_row["avg_buy_price"])
            old_total_cost = old_qty * old_avg_price

            if action_type.upper() in ["CASH_DIVIDEND", "CỔ TỨC TIỀN MẶT"]:
                # Tổng tiền cổ tức nhận được
                total_div_cash = cash_amount * old_qty
                new_avg_price = (old_total_cost - total_div_cash) / old_qty if old_qty > 0 else 0.0

                # Tăng tiền mặt tài khoản
                cash_row = conn.execute("SELECT cash_balance FROM account_cash_balance WHERE account_id = ?;", (account,)).fetchone()
                cur_cash = float(cash_row["cash_balance"]) if cash_row else 0.0
                new_cash = cur_cash + total_div_cash

                conn.execute("UPDATE account_cash_balance SET cash_balance = ?, updated_at = CURRENT_TIMESTAMP WHERE account_id = ?;", (new_cash, account))
                conn.execute("UPDATE portfolio SET avg_buy_price = ?, updated_at = CURRENT_TIMESTAMP WHERE account = ? AND ticker = ?;", (new_avg_price, account, ticker))

                conn.execute("""
                    INSERT INTO transactions (trade_date, account, type, symbol, cost, amount, total_amount, avg_price, comment)
                    VALUES (?, ?, 'Cổ tức bằng tiền', ?, ?, ?, ?, ?, ?);
                """, (ex_d, account, ticker, total_div_cash, total_div_cash, total_div_cash, new_avg_price, f"Cổ tức tiền mặt {ticker}: {cash_amount:,.0f} đ/CP"))
                conn.commit()

                return {"status": "SUCCESS", "ticker": ticker, "action": "CASH_DIVIDEND", "total_cash": total_div_cash, "new_avg_price": new_avg_price}

            elif action_type.upper() in ["STOCK_DIVIDEND", "BONUS_SHARES", "CỔ TỨC CỔ PHIẾU"]:
                bonus_qty = old_qty * ratio
                tax_5pct = (bonus_qty * 10000.0 * 0.05) if ex_dt >= tax_cutoff else 0.0

                new_qty = old_qty + bonus_qty
                new_avg_price = (old_total_cost + tax_5pct) / new_qty if new_qty > 0 else 0.0

                conn.execute("""
                    UPDATE portfolio 
                    SET quantity = ?, avg_buy_price = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE account = ? AND ticker = ?;
                """, (new_qty, new_avg_price, account, ticker))

                conn.execute("""
                    INSERT INTO transactions (trade_date, account, type, symbol, quantity, amount, total_amount, avg_price, comment)
                    VALUES (?, ?, 'Cổ tức bằng cổ phiếu', ?, ?, 0, 0, ?, ?);
                """, (ex_d, account, ticker, bonus_qty, new_avg_price, f"Cổ tức CP {ticker} tỷ lệ {ratio*100:.1f}%, thuế 5%: {tax_5pct:,.0f} đ"))
                conn.commit()

                return {"status": "SUCCESS", "ticker": ticker, "action": "STOCK_DIVIDEND", "bonus_qty": bonus_qty, "new_qty": new_qty, "new_avg_price": new_avg_price}

    def record_cash_flow(
        self,
        account: str,
        cash_type: str,
        amount: float,
        trade_date: Optional[str] = None,
        comment: Optional[str] = None
    ) -> float:
        """Nghiệp vụ Dòng tiền mặt thuần (Nộp tiền, Rút tiền, Tiền lãi, Phí lưu ký...)"""
        t_date = trade_date or date.today().strftime("%Y-%m-%d")
        with self.get_connection() as conn:
            cash_row = conn.execute("SELECT cash_balance FROM account_cash_balance WHERE account_id = ?;", (account,)).fetchone()
            cur_cash = float(cash_row["cash_balance"]) if cash_row else 0.0
            new_cash = cur_cash + amount

            conn.execute("""
                INSERT OR REPLACE INTO account_cash_balance (account_id, cash_balance, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP);
            """, (account, new_cash))

            conn.execute("""
                INSERT INTO transactions (trade_date, account, type, cost, amount, total_amount, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (t_date, account, cash_type, abs(amount), abs(amount), amount, comment or f"Biến động dòng tiền: {cash_type}"))
            conn.commit()
            return new_cash

    # ==========================================
    # CHỐT SỔ KẾ TOÁN NAV HÀNG NGÀY (EOD CHỐT SỔ)
    # ==========================================
    def close_daily_nav(
        self,
        trade_date: str,
        current_prices: Dict[str, float],
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Nghiệp vụ Chốt sổ NAV cuối ngày (Mark-to-Market Đa Tài khoản):
        1. Cập nhật giá đóng cửa hôm nay cho tất cả cổ phiếu trong danh mục mọi tài khoản
        2. Tính toán Lợi nhuận tạm tính (Unrealized PnL), Tổng tài sản ròng (NAV)
        3. Tính % Lãi/lỗ ngày so với hôm qua và NAV/share
        """
        with self.get_connection() as conn:
            # Lấy danh sách tài sản đóng băng từ DB
            susp_rows = conn.execute("""
                SELECT ticker, status, reason, provision_rate, recovery_estimated_price 
                FROM suspended_assets 
                WHERE status != 'ACTIVE';
            """).fetchall()
            susp_dict = {r["ticker"].upper(): dict(r) for r in susp_rows}

            total_stock_value = 0.0
            liquid_stock_value = 0.0
            frozen_assets_value = 0.0
            total_unrealized_pnl = 0.0
            total_provision_loss = 0.0
            core_stock_value = 0.0
            quant_stock_value = 0.0

            pf_rows = conn.execute("SELECT account, ticker, strategy_book, quantity, avg_buy_price FROM portfolio WHERE quantity > 0;").fetchall()
            for row in pf_rows:
                acc = row["account"]
                t = row["ticker"].upper()
                s_book = row["strategy_book"] if "strategy_book" in row.keys() else "QUANT"
                q = float(row["quantity"])
                avg_p = float(row["avg_buy_price"])

                # Cổ phiếu treo sàn/ngừng giao dịch / hủy niêm yết
                if t in susp_dict:
                    susp_info = susp_dict[t]
                    prov_rate = float(susp_info.get("provision_rate", 1.0))
                    recov_p = float(susp_info.get("recovery_estimated_price", 0.0))
                    # Nếu provision_rate = 1.0 -> định giá 0đ. Nếu có giá ước tính thu hồi hoặc trích lập 1 phần:
                    close_p = recov_p if prov_rate >= 1.0 else (avg_p * (1.0 - prov_rate))
                    mkt_val = q * close_p
                    unreal_pnl = mkt_val - (q * avg_p)
                    unreal_pct = -100.0 if prov_rate >= 1.0 else (-prov_rate * 100.0)
                    frozen_assets_value += mkt_val
                    total_provision_loss += (q * avg_p * prov_rate)
                else:
                    raw_close = current_prices.get(t, avg_p)
                    close_p = raw_close * 1000.0 if raw_close < 1000.0 else raw_close
                    mkt_val = q * close_p
                    unreal_pnl = mkt_val - (q * avg_p)
                    unreal_pct = (unreal_pnl / (q * avg_p)) * 100.0 if avg_p > 0 else 0.0
                    liquid_stock_value += mkt_val

                total_stock_value += mkt_val
                total_unrealized_pnl += unreal_pnl
                if s_book == "CORE":
                    core_stock_value += mkt_val
                else:
                    quant_stock_value += mkt_val

                conn.execute("""
                    UPDATE portfolio
                    SET current_price = ?, market_value = ?, 
                        unrealized_pnl = ?, unrealized_pnl_pct = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE account = ? AND ticker = ? AND strategy_book = ?;
                """, (close_p, mkt_val, unreal_pnl, unreal_pct, acc, t, s_book))

            # Lấy tổng số dư tiền mặt của tất cả tài khoản
            cash = self.get_current_cash()
            total_nav = cash + total_stock_value
            liquid_nav = cash + liquid_stock_value
            core_nav = core_stock_value + (cash * 0.70)
            quant_nav = quant_stock_value + (cash * 0.30)

            if total_nav > 0:
                conn.execute("""
                    UPDATE portfolio
                    SET weight_pct = (market_value / ?) * 100.0;
                """, (total_nav,))

            # Lấy NAV của ngày giao dịch trước đó
            prev_nav_row = conn.execute("""
                SELECT total_nav FROM nav_daily 
                WHERE trade_date < ? 
                ORDER BY trade_date DESC LIMIT 1;
            """, (trade_date,)).fetchone()

            prev_nav = float(prev_nav_row["total_nav"]) if prev_nav_row else total_nav
            daily_pnl = total_nav - prev_nav
            daily_pnl_pct = (daily_pnl / prev_nav) * 100.0 if prev_nav > 0 else 0.0

            # Tính lợi nhuận lũy kế thực tế từ giao dịch đã chốt
            pnl_row = conn.execute("SELECT SUM(profit) as total_profit FROM transactions WHERE profit IS NOT NULL;").fetchone()
            realized_pnl = float(pnl_row["total_profit"]) if pnl_row and pnl_row["total_profit"] is not None else 0.0
            cumulative_pnl = realized_pnl + total_unrealized_pnl

            conn.execute("""
                INSERT OR REPLACE INTO nav_daily (
                    trade_date, total_nav, cash_balance, stock_value, core_nav, quant_nav,
                    daily_pnl, daily_pnl_pct, cumulative_pnl, realized_pnl, unrealized_pnl,
                    liquid_nav, frozen_assets_value, provision_loss,
                    nav_per_share, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (
                trade_date, total_nav, cash, total_stock_value, core_nav, quant_nav,
                daily_pnl, daily_pnl_pct, cumulative_pnl, realized_pnl, total_unrealized_pnl,
                liquid_nav, frozen_assets_value, total_provision_loss,
                10000.0, notes
            ))

            conn.commit()

        return {
            "trade_date": trade_date,
            "total_nav": total_nav,
            "liquid_nav": liquid_nav,
            "frozen_assets_value": frozen_assets_value,
            "provision_loss": total_provision_loss,
            "cash_balance": cash,
            "stock_value": total_stock_value,
            "liquid_stock_value": liquid_stock_value,
            "core_nav": core_nav,
            "quant_nav": quant_nav,
            "daily_pnl": daily_pnl,
            "daily_pnl_pct": daily_pnl_pct,
            "cumulative_pnl": cumulative_pnl,
            "unrealized_pnl": total_unrealized_pnl
        }

    def get_latest_nav(self) -> Optional[Dict[str, Any]]:
        """Lấy thông tin NAV mới nhất của Quỹ"""
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM nav_daily 
                ORDER BY trade_date DESC, created_at DESC LIMIT 1;
            """).fetchone()
            return dict(row) if row else None

    def get_nav_history(self, limit: int = 90) -> List[Dict[str, Any]]:
        """Lấy chuỗi lịch sử NAV phục vụ vẽ biểu đồ Dashboard (Lấy limit phiên gần nhất, xếp theo ngày tăng dần)"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT trade_date, total_nav, cash_balance, stock_value, daily_pnl, daily_pnl_pct, cumulative_pnl
                FROM (
                    SELECT trade_date, total_nav, cash_balance, stock_value, daily_pnl, daily_pnl_pct, cumulative_pnl
                    FROM nav_daily
                    ORDER BY trade_date DESC
                    LIMIT ?
                )
                ORDER BY trade_date ASC;
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]

    def get_capital_summary(self, account: Optional[str] = None) -> Dict[str, Any]:
        """
        Tính toán Vốn Gốc Đầu Tư và Dòng Tiền theo chuẩn kế toán quản trị quỹ:
        - Vốn gốc (Principal) của mỗi tài khoản không bao giờ được âm.
        - Khi rút tiền > vốn gốc đã nộp: vốn gốc đưa về 0đ, phần vượt trội là Rút Lợi Nhuận (Profit Distribution).
        - Khi nộp tiền mới sau đó: tái khởi tạo vốn gốc mới = số tiền nộp mới.
        """
        with self.get_connection() as conn:
            acc_filter = "WHERE account = ?" if account and account != "ALL" else ""
            params = (account,) if account and account != "ALL" else ()

            rows = conn.execute(f"""
                SELECT account, trade_date, type, total_amount
                FROM transactions
                {acc_filter}
                {'AND' if acc_filter else 'WHERE'} type IN ('Nộp tiền', 'Rút tiền')
                ORDER BY trade_date ASC, id ASC;
            """, params).fetchall()

            acc_cap = {}
            acc_wdr_profit = {}
            total_dep = 0.0
            total_wdr = 0.0
            first_dep_date = None

            for r in rows:
                a = r["account"]
                if a not in acc_cap:
                    acc_cap[a] = 0.0
                    acc_wdr_profit[a] = 0.0
                amt = float(r["total_amount"])
                if r["type"] == "Nộp tiền":
                    total_dep += amt
                    acc_cap[a] += amt
                    if first_dep_date is None or r["trade_date"] < first_dep_date:
                        first_dep_date = r["trade_date"]
                elif r["type"] == "Rút tiền":
                    wdr = abs(amt)
                    total_wdr += wdr
                    if wdr <= acc_cap[a]:
                        acc_cap[a] -= wdr
                    else:
                        profit_wdr = wdr - acc_cap[a]
                        acc_wdr_profit[a] += profit_wdr
                        acc_cap[a] = 0.0

            active_capital = sum(acc_cap.values())
            profit_withdrawn = sum(acc_wdr_profit.values())
            net_cash_flow = total_dep - total_wdr

            # Lấy NAV hiện tại
            portfolio = self.get_portfolio(account=account)
            cash = self.get_current_cash(account=account)
            stock_value = sum(p["market_value"] for p in portfolio)
            current_nav = cash + stock_value

            # Lợi nhuận tổng thể = (NAV hiện tại - Vốn gốc đang gửi) + Lãi đã rút ra ngoài
            net_profit = (current_nav - active_capital) + profit_withdrawn
            base_cap = active_capital if active_capital > 0 else (net_cash_flow if net_cash_flow > 0 else total_dep)
            return_pct = (net_profit / base_cap * 100.0) if base_cap > 0 else 0.0

            # Lãi đã chốt (Realized PnL) và lãi tạm tính (Unrealized PnL) theo tài khoản
            acc_filter_tx = "WHERE account = ?" if account and account != "ALL" else ""
            pnl_row = conn.execute(f"""
                SELECT SUM(profit) as total_profit 
                FROM transactions 
                {acc_filter_tx}
                {'AND' if acc_filter_tx else 'WHERE'} profit IS NOT NULL;
            """, params).fetchone()
            realized_pnl = float(pnl_row["total_profit"]) if pnl_row and pnl_row["total_profit"] is not None else 0.0
            unrealized_pnl = sum(p["unrealized_pnl"] for p in portfolio)

            return {
                "account": account or "ALL",
                "total_deposited": total_dep,
                "total_withdrawn": total_wdr,
                "net_cash_flow": net_cash_flow,
                "active_capital": active_capital,
                "net_capital": active_capital,  # Vốn gốc đang đầu tư (không bao giờ âm)
                "profit_withdrawn": profit_withdrawn,
                "first_deposit_date": first_dep_date,
                "current_nav": current_nav,
                "cash_balance": cash,
                "stock_value": stock_value,
                "net_profit": net_profit,
                "return_pct": return_pct,
                "realized_pnl": realized_pnl,
                "unrealized_pnl": unrealized_pnl
            }

    # ==========================================
    # BIÊN BẢN HỌP HỘI ĐỒNG ĐẦU TƯ (DECISION MEMOS)
    # ==========================================
    def save_decision_memo(self, memo_data: Dict[str, Any]) -> str:
        """Lưu biên bản họp Ủy ban Đầu tư AI vào database"""
        memo_id = memo_data.get("memo_id") or f"MEMO-{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{memo_data.get('ticker', 'VN')}"
        trade_date = memo_data.get("trade_date") or date.today().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def _stringify(val):
            if isinstance(val, (dict, list)):
                return json.dumps(val, ensure_ascii=False)
            return str(val) if val is not None else ""

        with self.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(decision_memos);").fetchall()]
            if "jev_telemetry" in cols:
                conn.execute("""
                    INSERT OR REPLACE INTO decision_memos (
                        memo_id, ticker, strategy_book, trade_date, action, target_price, stop_loss_price,
                        target_volume, macro_view, fa_summary, ta_ml_summary, bull_arguments,
                        bear_arguments, cro_verdict, cro_position_size, cio_decision, status, jev_telemetry, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    memo_id,
                    memo_data.get("ticker", "").upper(),
                    memo_data.get("strategy_book", "QUANT").upper(),
                    trade_date,
                    memo_data.get("action", "BUY").upper(),
                    float(memo_data.get("target_price", 0.0)),
                    float(memo_data.get("stop_loss_price", 0.0)),
                    int(memo_data.get("target_volume", 0)),
                    _stringify(memo_data.get("macro_view", "")),
                    _stringify(memo_data.get("fa_summary", "")),
                    _stringify(memo_data.get("ta_ml_summary", "")),
                    _stringify(memo_data.get("bull_arguments", "")),
                    _stringify(memo_data.get("bear_arguments", "")),
                    _stringify(memo_data.get("cro_verdict", "APPROVED")),
                    float(memo_data.get("cro_position_size", 0.0)),
                    _stringify(memo_data.get("cio_decision", "")),
                    memo_data.get("status", "PROPOSED"),
                    _stringify(memo_data.get("jev_telemetry", {})),
                    now_str
                ))
            else:
                conn.execute("""
                    INSERT OR REPLACE INTO decision_memos (
                        memo_id, ticker, strategy_book, trade_date, action, target_price, stop_loss_price,
                        target_volume, macro_view, fa_summary, ta_ml_summary, bull_arguments,
                        bear_arguments, cro_verdict, cro_position_size, cio_decision, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    memo_id,
                    memo_data.get("ticker", "").upper(),
                    memo_data.get("strategy_book", "QUANT").upper(),
                    trade_date,
                    memo_data.get("action", "BUY").upper(),
                    float(memo_data.get("target_price", 0.0)),
                    float(memo_data.get("stop_loss_price", 0.0)),
                    int(memo_data.get("target_volume", 0)),
                    _stringify(memo_data.get("macro_view", "")),
                    _stringify(memo_data.get("fa_summary", "")),
                    _stringify(memo_data.get("ta_ml_summary", "")),
                    _stringify(memo_data.get("bull_arguments", "")),
                    _stringify(memo_data.get("bear_arguments", "")),
                    _stringify(memo_data.get("cro_verdict", "APPROVED")),
                    float(memo_data.get("cro_position_size", 0.0)),
                    _stringify(memo_data.get("cio_decision", "")),
                    memo_data.get("status", "PROPOSED"),
                    now_str
                ))
            conn.commit()
        return memo_id

    @staticmethod
    def _parse_memo_row(r) -> Dict[str, Any]:
        d = dict(r)
        json_cols = ['macro_view', 'fa_summary', 'ta_ml_summary', 'bull_arguments', 'bear_arguments', 'cro_verdict', 'cio_decision', 'jev_telemetry']
        for c in json_cols:
            val = d.get(c)
            if isinstance(val, str) and (val.strip().startswith('{') or val.strip().startswith('[')):
                try:
                    d[c] = json.loads(val)
                except Exception:
                    pass
        return d

    def get_decision_memos(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Lấy danh sách các biên bản họp Ủy ban Đầu tư"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM decision_memos 
                ORDER BY created_at DESC 
                LIMIT ?;
            """, (limit,)).fetchall()
            return [self._parse_memo_row(r) for r in rows]

    def get_decision_memo_by_id(self, memo_id: str) -> Optional[Dict[str, Any]]:
        """Lấy chi tiết biên bản họp theo memo_id"""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM decision_memos WHERE memo_id = ?;", (memo_id,)).fetchone()
            return self._parse_memo_row(row) if row else None

    def update_memo_status(self, memo_id: str, status: str, notes: Optional[str] = None) -> bool:
        """Cập nhật trạng thái phê duyệt của Tờ trình (APPROVED / REJECTED)"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE decision_memos 
                SET status = ? 
                WHERE memo_id = ?;
            """, (status.upper(), memo_id))
            # Nếu có liên kết với order_history, đồng bộ trạng thái lệnh
            order_status = "SUBMITTED" if status.upper() == "APPROVED" else ("CANCELLED" if status.upper() == "REJECTED" else None)
            if order_status:
                conn.execute("""
                    UPDATE order_history 
                    SET status = ? 
                    WHERE memo_id = ?;
                """, (order_status, memo_id))
            conn.commit()
            return True

    def record_corporate_action(
        self,
        ticker: str,
        action_type: str,  # 'CASH_DIVIDEND', 'STOCK_DIVIDEND', 'BONUS_SHARES', 'RIGHT_ISSUE'
        ex_date: str,
        account: str = "0001716319",
        strategy_book: Optional[str] = None,
        cash_amount_per_share: float = 0.0,
        ratio: float = 0.0,
        tax_rate: float = 0.05,
        record_date: Optional[str] = None,
        payment_date: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Nghiệp vụ Hạch toán Sự kiện Doanh nghiệp & Quyền Cổ tức (Corporate Actions):
        1. CỔ TỨC TIỀN MẶT ('CASH_DIVIDEND'):
           - Tiền nhận gộp = Khối lượng nắm giữ * cash_amount_per_share
           - Thuế TNCN cổ tức tiền = Tiền nhận gộp * 5% (tax_rate)
           - Tiền thực nhận vào số dư = Tiền nhận gộp - Thuế
           - Tăng số dư tiền mặt tài khoản (account_cash_balance)
           - Ghi sổ nhật ký giao dịch (transactions: type='Cổ tức tiền')
        2. CỔ TỨC CỔ PHIẾU / CỔ PHIẾU THƯỞNG ('STOCK_DIVIDEND', 'BONUS_SHARES'):
           - Số lượng cổ phiếu thưởng = int(Khối lượng cũ * ratio)
           - Khối lượng mới = Khối lượng cũ + Số lượng thưởng
           - Giá vốn bình quân pha loãng = (Khối lượng cũ * Giá vốn cũ) / Khối lượng mới
           - Cập nhật danh mục portfolio với giá vốn mới
           - Ghi sổ nhật ký giao dịch (transactions: type='Cổ tức CP')
        3. Lưu vết vĩnh viễn vào bảng corporate_actions với trạng thái 'APPLIED'
        """
        t = ticker.upper()
        act = action_type.upper()
        p_date = payment_date or ex_date
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.get_connection() as conn:
            query_pf = "SELECT * FROM portfolio WHERE ticker = ? AND quantity > 0"
            params_pf = [t]
            if account:
                query_pf += " AND account = ?"
                params_pf.append(account)
            if strategy_book:
                query_pf += " AND strategy_book = ?"
                params_pf.append(strategy_book.upper())

            positions = conn.execute(query_pf, params_pf).fetchall()
            if not positions:
                raise ValueError(f"Không tìm thấy vị thế nắm giữ mã {t} trong danh mục để hạch toán cổ tức/quyền.")

            total_shares_eligible = sum(float(p["quantity"]) for p in positions)
            applied_details = []

            gross_cash = 0.0
            tax_cash = 0.0
            net_cash = 0.0
            total_bonus_shares = 0

            if act == "CASH_DIVIDEND":
                gross_cash = total_shares_eligible * cash_amount_per_share
                tax_cash = gross_cash * tax_rate
                net_cash = gross_cash - tax_cash

                # Tăng tiền mặt vào tài khoản
                cash_row = conn.execute("SELECT cash_balance FROM account_cash_balance WHERE account_id = ?;", (account,)).fetchone()
                curr_cash = float(cash_row["cash_balance"]) if cash_row else 0.0
                new_cash = curr_cash + net_cash
                conn.execute("""
                    INSERT INTO account_cash_balance (account_id, cash_balance, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(account_id) DO UPDATE SET
                        cash_balance = excluded.cash_balance,
                        updated_at = CURRENT_TIMESTAMP;
                """, (account, new_cash))

                tx_comment = notes or f"Nhận cổ tức tiền {t}: {cash_amount_per_share:,.0f} đ/CP x {total_shares_eligible:,.0f} CP (Thuế 5%: {tax_cash:,.0f} đ)"
                conn.execute("""
                    INSERT INTO transactions (
                        trade_date, money_date, symbol_date, account, type, symbol,
                        quantity, cost, fee, tax, amount, total_amount, comment
                    ) VALUES (?, ?, ?, ?, 'Cổ tức tiền', ?, ?, ?, 0.0, ?, ?, ?, ?);
                """, (ex_date, p_date, ex_date, account, t, total_shares_eligible, cash_amount_per_share, tax_cash, gross_cash, net_cash, tx_comment))

                applied_details.append({
                    "type": "CASH_DIVIDEND",
                    "shares_held": total_shares_eligible,
                    "gross_cash": gross_cash,
                    "tax": tax_cash,
                    "net_cash": net_cash
                })

            elif act in ("STOCK_DIVIDEND", "BONUS_SHARES"):
                for pos in positions:
                    pos_account = pos["account"]
                    pos_book = pos["strategy_book"]
                    old_qty = float(pos["quantity"])
                    old_avg_price = float(pos["avg_buy_price"])

                    bonus_qty = int(old_qty * ratio)
                    if bonus_qty <= 0:
                        continue

                    new_qty = old_qty + bonus_qty
                    # CÔNG THỨC PHA LOÃNG GIÁ VỐN CHUẨN
                    new_avg_price = (old_qty * old_avg_price) / new_qty
                    curr_price = float(pos["current_price"]) if pos["current_price"] else old_avg_price
                    new_market_val = new_qty * curr_price
                    new_unrealized_pnl = new_market_val - (new_qty * new_avg_price)
                    new_pnl_pct = (new_unrealized_pnl / (new_qty * new_avg_price)) * 100.0 if new_avg_price > 0 else 0.0

                    conn.execute("""
                        UPDATE portfolio
                        SET quantity = ?, avg_buy_price = ?, market_value = ?,
                            unrealized_pnl = ?, unrealized_pnl_pct = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE account = ? AND ticker = ? AND strategy_book = ?;
                    """, (new_qty, new_avg_price, new_market_val, new_unrealized_pnl, new_pnl_pct, pos_account, t, pos_book))

                    total_bonus_shares += bonus_qty
                    tx_comment = notes or f"Nhận cổ tức CP {t} ({ratio*100:.1f}%): +{bonus_qty:,} CP, giá vốn pha loãng {old_avg_price:,.0f} -> {new_avg_price:,.0f} đ"
                    conn.execute("""
                        INSERT INTO transactions (
                            trade_date, money_date, symbol_date, account, type, symbol,
                            quantity, cost, fee, tax, amount, total_amount, avg_price, comment
                        ) VALUES (?, ?, ?, ?, 'Cổ tức CP', ?, ?, 0.0, 0.0, 0.0, 0.0, 0.0, ?, ?);
                    """, (ex_date, ex_date, p_date, pos_account, t, bonus_qty, new_avg_price, tx_comment))

                    applied_details.append({
                        "account": pos_account,
                        "strategy_book": pos_book,
                        "old_qty": old_qty,
                        "bonus_qty": bonus_qty,
                        "new_qty": new_qty,
                        "old_avg_price": old_avg_price,
                        "new_avg_price": new_avg_price
                    })

            cur = conn.execute("""
                INSERT INTO corporate_actions (
                    ticker, action_type, ex_date, record_date, payment_date,
                    ratio, cash_amount_per_share, status, applied_at, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'APPLIED', ?, ?);
            """, (t, act, ex_date, record_date, p_date, ratio, cash_amount_per_share, now_str, notes))
            action_id = cur.lastrowid
            conn.commit()

            return {
                "action_id": action_id,
                "ticker": t,
                "action_type": act,
                "ex_date": ex_date,
                "total_shares_eligible": total_shares_eligible,
                "gross_cash": gross_cash,
                "tax_cash": tax_cash,
                "net_cash": net_cash,
                "total_bonus_shares": total_bonus_shares,
                "applied_details": applied_details,
                "status": "APPLIED"
            }

    def get_corporate_actions(self, ticker: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Lấy danh sách các sự kiện quyền & cổ tức đã lưu"""
        with self.get_connection() as conn:
            if ticker:
                rows = conn.execute("""
                    SELECT * FROM corporate_actions 
                    WHERE ticker = ? 
                    ORDER BY ex_date DESC, id DESC 
                    LIMIT ?;
                """, (ticker.upper(), limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM corporate_actions 
                    ORDER BY ex_date DESC, id DESC 
                    LIMIT ?;
                """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ==========================================
    # DỮ LIỆU TÀI CHÍNH CƠ BẢN (COMPANY FUNDAMENTALS)
    # ==========================================
    def upsert_fundamental(self, metrics: Dict[str, Any]) -> bool:
        """Thêm hoặc cập nhật chỉ số tài chính cơ bản cho một mã cổ phiếu vào SQLite"""
        t = metrics["ticker"].upper()
        period = metrics.get("period") or f"{metrics.get('year', 2026)}Q{metrics.get('quarter', 3)}"
        year = int(metrics.get("year", 2026))
        quarter = int(metrics.get("quarter", 3))

        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO company_fundamentals (
                    ticker, period, year, quarter, revenue_growth_yoy, profit_growth_yoy,
                    roe, gross_margin, debt_to_equity, ocf_to_net_income, pe, pb,
                    pe_5y_median, piotroski_f_score, altman_z_score, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(ticker, period) DO UPDATE SET
                    revenue_growth_yoy = excluded.revenue_growth_yoy,
                    profit_growth_yoy = excluded.profit_growth_yoy,
                    roe = excluded.roe,
                    gross_margin = excluded.gross_margin,
                    debt_to_equity = excluded.debt_to_equity,
                    ocf_to_net_income = excluded.ocf_to_net_income,
                    pe = excluded.pe,
                    pb = excluded.pb,
                    pe_5y_median = excluded.pe_5y_median,
                    piotroski_f_score = excluded.piotroski_f_score,
                    altman_z_score = excluded.altman_z_score,
                    notes = excluded.notes,
                    updated_at = CURRENT_TIMESTAMP;
            """, (
                t, period, year, quarter,
                float(metrics.get("revenue_growth_yoy", 0.0)),
                float(metrics.get("profit_growth_yoy", 0.0)),
                float(metrics.get("roe", 0.0)),
                float(metrics.get("gross_margin", 0.0)),
                float(metrics.get("debt_to_equity", 0.0)),
                float(metrics.get("ocf_to_net_income", 1.0)),
                float(metrics.get("pe", 15.0)),
                float(metrics.get("pb", 1.5)),
                float(metrics.get("pe_5y_median", 15.0)),
                int(metrics.get("piotroski_f_score", 6)),
                float(metrics.get("altman_z_score", 2.6)),
                metrics.get("notes")
            ))
            conn.commit()
        return True

    def bulk_upsert_fundamentals(self, records: List[Dict[str, Any]]) -> int:
        """Nạp hàng loạt dữ liệu tài chính BCTC vào SQLite"""
        count = 0
        for r in records:
            if self.upsert_fundamental(r):
                count += 1
        return count

    def get_latest_fundamental(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Lấy chỉ số BCTC mới nhất của một mã cổ phiếu từ SQLite"""
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM company_fundamentals
                WHERE ticker = ?
                ORDER BY year DESC, quarter DESC, updated_at DESC LIMIT 1;
            """, (ticker.upper(),)).fetchone()
            return dict(row) if row else None

    def get_all_fundamentals(self, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lấy danh sách tất cả chỉ số BCTC từ SQLite"""
        with self.get_connection() as conn:
            if ticker:
                rows = conn.execute("""
                    SELECT * FROM company_fundamentals
                    WHERE ticker = ?
                    ORDER BY year DESC, quarter DESC;
                """, (ticker.upper(),)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM company_fundamentals
                    ORDER BY ticker ASC, year DESC, quarter DESC;
                """).fetchall()
            return [dict(row) for row in rows]

"""
Module Quản trị Cơ sở Dữ liệu Quỹ (Database Manager).
Thực thi các nghiệp vụ Kế toán Quỹ Đa Tài khoản, Sổ lệnh, Danh mục, Cổ tức và Chốt NAV chuẩn xác.
"""

import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from config import settings

class DatabaseManager:
    """Quản trị viên Cơ sở Dữ liệu SQLite fund_vault.db"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.SQLITE_DB_PATH
        self.schema_path = settings.DATABASE_DIR / "schema.sql"
        self._ensure_db()

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

    def get_portfolio(self, account: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lấy danh mục cổ phiếu đang nắm giữ (hỗ trợ lọc theo tài khoản hoặc toàn quỹ)"""
        with self.get_connection() as conn:
            if account and account != "ALL":
                rows = conn.execute("""
                    SELECT account, ticker, quantity, avg_buy_price, current_price, market_value,
                           unrealized_pnl, unrealized_pnl_pct, weight_pct, first_bought_date, updated_at
                    FROM portfolio 
                    WHERE quantity > 0 AND account = ?
                    ORDER BY market_value DESC;
                """, (account,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT account, ticker, quantity, avg_buy_price, current_price, market_value,
                           unrealized_pnl, unrealized_pnl_pct, weight_pct, first_bought_date, updated_at
                    FROM portfolio 
                    WHERE quantity > 0
                    ORDER BY (account = '0001716319') DESC, market_value DESC;
                """).fetchall()
            return [dict(row) for row in rows]


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
        account: str = "0001716319"
    ) -> str:
        """AI tạo lệnh đề xuất gửi Telegram cho Bạn"""
        norm_proposed_price = proposed_price * 1000.0 if proposed_price < 1000.0 else proposed_price
        t_date = trade_date or date.today().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{ticker}"

        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO order_history (
                    order_id, account, ticker, action, order_type, proposed_price, proposed_volume,
                    status, trade_date, memo_id, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PROPOSED', ?, ?, ?, ?);
            """, (order_id, account, ticker.upper(), action.upper(), order_type, norm_proposed_price, proposed_volume, t_date, memo_id, notes, now_str))
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
                conn, ticker, action, norm_executed_price, executed_volume, fee, tax, order["trade_date"], account=account
            )
            conn.commit()

        return {
            "order_id": order_id,
            "account": account,
            "ticker": ticker,
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
        account: str = "0001716319"
    ) -> str:
        """Cơ chế Nhập bù trực tiếp: Nhập bù lệnh khớp từ app CTCK"""
        norm_executed_price = executed_price * 1000.0 if executed_price < 1000.0 else executed_price
        t_date = trade_date or date.today().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_id = f"FILL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{ticker.upper()}"

        with self.get_connection() as conn:
            acc_row = conn.execute("SELECT fee_rate FROM broker_accounts WHERE account_id = ?;", (account,)).fetchone()
            fee_rate = float(acc_row["fee_rate"]) if acc_row else settings.BROKER_FEE_RATE

            trade_value = norm_executed_price * executed_volume
            fee = trade_value * fee_rate
            tax = trade_value * settings.SELL_TAX_RATE if action.upper() == "SELL" else 0.0

            conn.execute("""
                INSERT INTO order_history (
                    order_id, account, ticker, action, order_type, proposed_price, proposed_volume,
                    executed_price, executed_volume, status, fee, tax, slippage_pct,
                    trade_date, created_at, executed_at, notes
                ) VALUES (?, ?, ?, ?, 'LO', ?, ?, ?, ?, 'FILLED', ?, ?, 0.0, ?, ?, ?, ?);
            """, (order_id, account, ticker.upper(), action.upper(), norm_executed_price, executed_volume,
                  norm_executed_price, executed_volume, fee, tax, t_date, now_str, now_str, notes))

            self._apply_trade_to_portfolio_and_cash(
                conn, ticker.upper(), action.upper(), norm_executed_price, executed_volume, fee, tax, t_date, account=account
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
        account: str = "0001716319"
    ):
        """
        Nghiệp vụ hạch toán biến động cổ phiếu và tiền mặt trong cùng 1 transaction:
        - Mua: Gộp phí mua vào giá vốn Avg Price: ((Q_cũ * Avg_cũ) + (Q_mua * P_mua) + Phí_mua) / (Q_cũ + Q_mua)
        - Bán: Tính chuẩn Realized Profit = Tiền thực nhận - (Q_bán * Avg_cũ); Avg Price giữ nguyên.
        """
        # Lấy số dư tiền mặt của tài khoản
        cash_row = conn.execute("SELECT cash_balance FROM account_cash_balance WHERE account_id = ?;", (account,)).fetchone()
        current_acc_cash = float(cash_row["cash_balance"]) if cash_row else 0.0

        # Lấy vị thế hiện tại của cổ phiếu trong tài khoản này
        pf_row = conn.execute("SELECT * FROM portfolio WHERE account = ? AND ticker = ?;", (account, ticker)).fetchone()

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
                    WHERE account = ? AND ticker = ?;
                """, (new_qty, new_avg_price, price, market_val, market_val - (new_qty * new_avg_price), account, ticker))
            else:
                new_avg_price = ((volume * price) + fee) / volume if volume > 0 else price
                market_val = volume * price
                calc_avg_price = new_avg_price

                conn.execute("""
                    INSERT INTO portfolio (
                        account, ticker, quantity, avg_buy_price, current_price, market_value,
                        unrealized_pnl, unrealized_pnl_pct, first_bought_date, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 0.0, 0.0, ?, CURRENT_TIMESTAMP);
                """, (account, ticker, volume, new_avg_price, price, market_val, trade_date))

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
                    conn.execute("DELETE FROM portfolio WHERE account = ? AND ticker = ?;", (account, ticker))
                else:
                    market_val = new_qty * price
                    conn.execute("""
                        UPDATE portfolio
                        SET quantity = ?, current_price = ?, market_value = ?,
                            unrealized_pnl = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE account = ? AND ticker = ?;
                    """, (new_qty, price, market_val, market_val - (new_qty * old_avg_price), account, ticker))

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
              price * volume, tot_amount, calc_avg_price, calc_profit, calc_profit_pct, f"Khớp lệnh {action} {ticker}"))

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
            SUSPENDED_TICKERS = {"FLC"}
            total_stock_value = 0.0
            total_unrealized_pnl = 0.0

            pf_rows = conn.execute("SELECT account, ticker, quantity, avg_buy_price FROM portfolio WHERE quantity > 0;").fetchall()
            for row in pf_rows:
                acc = row["account"]
                t = row["ticker"]
                q = float(row["quantity"])
                avg_p = float(row["avg_buy_price"])

                # Cổ phiếu treo sàn/ngừng giao dịch định giá 0đ
                if t in SUSPENDED_TICKERS:
                    close_p = 0.0
                    mkt_val = 0.0
                    unreal_pnl = - (q * avg_p)
                    unreal_pct = -100.0
                else:
                    raw_close = current_prices.get(t, avg_p)
                    close_p = raw_close * 1000.0 if raw_close < 1000.0 else raw_close
                    mkt_val = q * close_p
                    unreal_pnl = mkt_val - (q * avg_p)
                    unreal_pct = (unreal_pnl / (q * avg_p)) * 100.0 if avg_p > 0 else 0.0

                total_stock_value += mkt_val
                total_unrealized_pnl += unreal_pnl

                conn.execute("""
                    UPDATE portfolio
                    SET current_price = ?, market_value = ?, 
                        unrealized_pnl = ?, unrealized_pnl_pct = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE account = ? AND ticker = ?;
                """, (close_p, mkt_val, unreal_pnl, unreal_pct, acc, t))

            # Lấy tổng số dư tiền mặt của tất cả tài khoản
            cash = self.get_current_cash()
            total_nav = cash + total_stock_value

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
                    trade_date, total_nav, cash_balance, stock_value,
                    daily_pnl, daily_pnl_pct, cumulative_pnl, realized_pnl, unrealized_pnl,
                    nav_per_share, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (
                trade_date, total_nav, cash, total_stock_value,
                daily_pnl, daily_pnl_pct, cumulative_pnl, realized_pnl, total_unrealized_pnl,
                10000.0, notes
            ))

            conn.commit()

        return {
            "trade_date": trade_date,
            "total_nav": total_nav,
            "cash_balance": cash,
            "stock_value": total_stock_value,
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

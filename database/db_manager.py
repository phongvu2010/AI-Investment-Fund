"""
Module Quản trị Cơ sở Dữ liệu Quỹ (Database Manager).
Thực thi các nghiệp vụ Kế toán Quỹ, Sổ lệnh, Danh mục và Chốt NAV chuẩn xác.
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
                    ('initial_capital', ?, 'Vốn khởi lập của Quỹ (VND)', ?),
                    ('fund_status', 'ACTIVE', 'Trạng thái hoạt động của Quỹ', ?),
                    ('base_currency', 'VND', 'Đơn vị tiền tệ cơ sở', ?),
                    ('last_bigquery_sync', '', 'Thời điểm đồng bộ BigQuery gần nhất', ?);
            """, (str(initial_capital), now_str, now_str, now_str, now_str))

            # Khởi tạo bản ghi NAV ngày 0 (Chỉ có tiền mặt = initial_capital, chưa mua cổ phiếu nào)
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
    # TIỀN MẶT & DANH MỤC (PORTFOLIO)
    # ==========================================
    def get_current_cash(self) -> float:
        """Lấy số dư tiền mặt hiện tại từ bản ghi NAV gần nhất"""
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT cash_balance FROM nav_daily 
                ORDER BY trade_date DESC, created_at DESC LIMIT 1;
            """).fetchone()
            if row:
                return float(row["cash_balance"])
            return settings.INITIAL_CAPITAL

    def get_portfolio(self) -> List[Dict[str, Any]]:
        """Lấy toàn bộ danh mục cổ phiếu đang nắm giữ"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT ticker, quantity, avg_buy_price, current_price, market_value,
                       unrealized_pnl, unrealized_pnl_pct, weight_pct, first_bought_date, updated_at
                FROM portfolio 
                WHERE quantity > 0
                ORDER BY market_value DESC;
            """).fetchall()
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
        trade_date: Optional[str] = None
    ) -> str:
        """AI tạo lệnh đề xuất gửi Telegram cho Bạn"""
        t_date = trade_date or date.today().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{ticker}"

        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO order_history (
                    order_id, ticker, action, order_type, proposed_price, proposed_volume,
                    status, trade_date, memo_id, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'PROPOSED', ?, ?, ?, ?);
            """, (order_id, ticker.upper(), action.upper(), order_type, proposed_price, proposed_volume, t_date, memo_id, notes, now_str))
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
        2. Tính toán phí CTCK (0.15%), thuế TNCN (0.1% nếu bán), trượt giá (Slippage)
        3. Cập nhật số dư tiền mặt & danh mục cổ phiếu
        """
        now_str = executed_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.get_connection() as conn:
            # Lấy thông tin lệnh gốc
            order = conn.execute("SELECT * FROM order_history WHERE order_id = ?;", (order_id,)).fetchone()
            if not order:
                raise ValueError(f"Không tìm thấy lệnh với ID: {order_id}")

            ticker = order["ticker"]
            action = order["action"]
            proposed_price = order["proposed_price"]
            proposed_volume = order["proposed_volume"]

            # Tính phí và thuế
            trade_value = executed_price * executed_volume
            fee = trade_value * settings.BROKER_FEE_RATE
            tax = trade_value * settings.SELL_TAX_RATE if action == "SELL" else 0.0

            # Tính trượt giá (Slippage %)
            slippage_pct = ((executed_price - proposed_price) / proposed_price) * 100.0 if proposed_price > 0 else 0.0

            # Xác định trạng thái lệnh
            status = "FILLED" if executed_volume >= proposed_volume else "PARTIALLY_FILLED"

            # 1. Cập nhật sổ lệnh
            conn.execute("""
                UPDATE order_history
                SET executed_price = ?, executed_volume = ?, status = ?,
                    fee = ?, tax = ?, slippage_pct = ?, executed_at = ?, notes = COALESCE(?, notes)
                WHERE order_id = ?;
            """, (executed_price, executed_volume, status, fee, tax, slippage_pct, now_str, notes, order_id))

            # 2. Cập nhật Danh mục & Tiền mặt
            self._apply_trade_to_portfolio_and_cash(conn, ticker, action, executed_price, executed_volume, fee, tax, order["trade_date"])

            conn.commit()

        return {
            "order_id": order_id,
            "ticker": ticker,
            "action": action,
            "executed_price": executed_price,
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
        notes: str = "Nhập bù thủ công qua Telegram"
    ) -> str:
        """
        Cơ chế Nhập bù trực tiếp:
        Dùng khi Bạn quên bấm xác nhận lúc 15h, tối hoặc sáng hôm sau nhập bù qua cú pháp /fill.
        """
        t_date = trade_date or date.today().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_id = f"FILL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{ticker.upper()}"

        with self.get_connection() as conn:
            # Tạo bản ghi lệnh với trạng thái FILLED
            trade_value = executed_price * executed_volume
            fee = trade_value * settings.BROKER_FEE_RATE
            tax = trade_value * settings.SELL_TAX_RATE if action.upper() == "SELL" else 0.0

            conn.execute("""
                INSERT INTO order_history (
                    order_id, ticker, action, order_type, proposed_price, proposed_volume,
                    executed_price, executed_volume, status, fee, tax, slippage_pct,
                    trade_date, created_at, executed_at, notes
                ) VALUES (?, ?, ?, 'LO', ?, ?, ?, ?, 'FILLED', ?, ?, 0.0, ?, ?, ?, ?);
            """, (order_id, ticker.upper(), action.upper(), executed_price, executed_volume,
                  executed_price, executed_volume, fee, tax, t_date, now_str, now_str, notes))

            # Áp dụng thay đổi vào danh mục và tiền mặt
            self._apply_trade_to_portfolio_and_cash(conn, ticker.upper(), action.upper(), executed_price, executed_volume, fee, tax, t_date)
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
        trade_date: str
    ):
        """Nghiệp vụ hạch toán biến động cổ phiếu và tiền mặt trong cùng 1 transaction"""
        # Lấy bản ghi NAV gần nhất để cập nhật tiền mặt
        nav_row = conn.execute("""
            SELECT total_nav, cash_balance, stock_value, cumulative_pnl 
            FROM nav_daily ORDER BY trade_date DESC, created_at DESC LIMIT 1;
        """).fetchone()

        current_cash = float(nav_row["cash_balance"]) if nav_row else settings.INITIAL_CAPITAL
        total_pnl = float(nav_row["cumulative_pnl"]) if nav_row else 0.0

        # Lấy vị thế hiện tại của cổ phiếu
        pf_row = conn.execute("SELECT * FROM portfolio WHERE ticker = ?;", (ticker,)).fetchone()

        if action == "BUY":
            # TIỀN MẶT GIẢM = (Giá * Khối lượng) + Phí
            cash_outflow = (price * volume) + fee
            new_cash = current_cash - cash_outflow

            if pf_row:
                old_qty = int(pf_row["quantity"])
                old_avg_price = float(pf_row["avg_buy_price"])
                new_qty = old_qty + volume
                # Giá vốn bình quân gia quyền mới (Weighted Average Cost)
                new_avg_price = ((old_qty * old_avg_price) + (volume * price)) / new_qty
                market_val = new_qty * price

                conn.execute("""
                    UPDATE portfolio
                    SET quantity = ?, avg_buy_price = ?, current_price = ?, market_value = ?,
                        unrealized_pnl = ?, unrealized_pnl_pct = 0.0, updated_at = CURRENT_TIMESTAMP
                    WHERE ticker = ?;
                """, (new_qty, new_avg_price, price, market_val, market_val - (new_qty * new_avg_price), ticker))
            else:
                market_val = volume * price
                conn.execute("""
                    INSERT INTO portfolio (
                        ticker, quantity, avg_buy_price, current_price, market_value,
                        unrealized_pnl, unrealized_pnl_pct, first_bought_date, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 0.0, 0.0, ?, CURRENT_TIMESTAMP);
                """, (ticker, volume, price, price, market_val, trade_date))

        elif action == "SELL":
            # TIỀN MẶT TĂNG = (Giá * Khối lượng) - (Phí + Thuế)
            cash_inflow = (price * volume) - (fee + tax)
            new_cash = current_cash + cash_inflow

            if pf_row:
                old_qty = int(pf_row["quantity"])
                old_avg_price = float(pf_row["avg_buy_price"])
                new_qty = max(0, old_qty - volume)

                # Tính Realized PnL của thương vụ
                realized_gain = (price - old_avg_price) * volume - (fee + tax)
                total_pnl += realized_gain

                if new_qty == 0:
                    conn.execute("DELETE FROM portfolio WHERE ticker = ?;", (ticker,))
                else:
                    market_val = new_qty * price
                    conn.execute("""
                        UPDATE portfolio
                        SET quantity = ?, current_price = ?, market_value = ?,
                            unrealized_pnl = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE ticker = ?;
                    """, (new_qty, price, market_val, market_val - (new_qty * old_avg_price), ticker))

        # Cập nhật số dư tiền mặt tức thời vào bản ghi nav_daily hôm nay
        conn.execute("""
            UPDATE nav_daily 
            SET cash_balance = ?, cumulative_pnl = ?
            WHERE trade_date = (SELECT MAX(trade_date) FROM nav_daily);
        """, (new_cash, total_pnl))

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
        Nghiệp vụ Chốt sổ NAV cuối ngày (Mark-to-Market):
        1. Cập nhật giá đóng cửa hôm nay cho tất cả cổ phiếu trong danh mục
        2. Tính toán Lợi nhuận tạm tính (Unrealized PnL), Tổng tài sản ròng (NAV)
        3. Tính % Lãi/lỗ ngày so với hôm qua và NAV/share
        """
        with self.get_connection() as conn:
            # 1. Cập nhật giá thị trường cho danh mục
            total_stock_value = 0.0
            total_unrealized_pnl = 0.0

            pf_rows = conn.execute("SELECT ticker, quantity, avg_buy_price FROM portfolio WHERE quantity > 0;").fetchall()
            for row in pf_rows:
                t = row["ticker"]
                q = int(row["quantity"])
                avg_p = float(row["avg_buy_price"])
                # Lấy giá đóng cửa mới nhất, nếu không có thì giữ giá vốn
                close_p = current_prices.get(t, avg_p)

                mkt_val = q * close_p
                unreal_pnl = mkt_val - (q * avg_p)
                unreal_pct = (unreal_pnl / (q * avg_p)) * 100.0 if avg_p > 0 else 0.0

                total_stock_value += mkt_val
                total_unrealized_pnl += unreal_pnl

                conn.execute("""
                    UPDATE portfolio
                    SET current_price = ?, market_value = ?, 
                        unrealized_pnl = ?, unrealized_pnl_pct = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE ticker = ?;
                """, (close_p, mkt_val, unreal_pnl, unreal_pct, t))

            # 2. Lấy số dư tiền mặt hiện tại
            cash = self.get_current_cash()
            total_nav = cash + total_stock_value

            # 3. Tính tỷ trọng % cho từng mã
            if total_nav > 0:
                conn.execute("""
                    UPDATE portfolio
                    SET weight_pct = (market_value / ?) * 100.0;
                """, (total_nav,))

            # 4. Lấy NAV của ngày giao dịch trước đó để tính Daily PnL
            prev_nav_row = conn.execute("""
                SELECT total_nav FROM nav_daily 
                WHERE trade_date < ? 
                ORDER BY trade_date DESC LIMIT 1;
            """, (trade_date,)).fetchone()

            prev_nav = float(prev_nav_row["total_nav"]) if prev_nav_row else settings.INITIAL_CAPITAL
            daily_pnl = total_nav - prev_nav
            daily_pnl_pct = (daily_pnl / prev_nav) * 100.0 if prev_nav > 0 else 0.0
            cumulative_pnl = total_nav - settings.INITIAL_CAPITAL

            # 5. Lưu hoặc cập nhật bản ghi chốt sổ ngày
            conn.execute("""
                INSERT OR REPLACE INTO nav_daily (
                    trade_date, total_nav, cash_balance, stock_value,
                    daily_pnl, daily_pnl_pct, cumulative_pnl, unrealized_pnl,
                    nav_per_share, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (
                trade_date, total_nav, cash, total_stock_value,
                daily_pnl, daily_pnl_pct, cumulative_pnl, total_unrealized_pnl,
                (total_nav / settings.INITIAL_CAPITAL) * 10000.0, notes
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
        """Lấy chuỗi lịch sử NAV phục vụ vẽ biểu đồ Dashboard (0 Token)"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT trade_date, total_nav, cash_balance, stock_value, daily_pnl, daily_pnl_pct, cumulative_pnl
                FROM nav_daily
                ORDER BY trade_date ASC
                LIMIT ?;
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]

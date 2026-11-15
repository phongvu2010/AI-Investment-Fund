"""
Module Nhập liệu & Tái hiện Kế toán Lịch sử (Transaction Importer & Accounting Engine).
Replay 1.710 giao dịch thực tế từ 16/06/2016 đến nay qua 4 tài khoản CTCK:
0001716319, 009C105992, 127008, 123C006116.

Chuẩn hóa 100% công thức:
- Avg Price: Bình quân gia quyền gộp phí mua.
- Cổ tức tiền mặt: Khấu trừ trực tiếp vào giá vốn (Avg Price cũ * Q cũ - Tiền cổ tức) / Q cũ.
- Cổ tức cổ phiếu: Pha loãng giá vốn. Từ 05/12/2020 tính thêm thuế 5% trên mệnh giá 10k:
  (Avg Price cũ * Q cũ + Thuế 5%) / (Q cũ + Q thưởng).
- Profit & Profit %: Tính chuẩn xác theo giá vốn bình quân thực tế trước bán.
- Cash Balance: Quản lý số dư tiền mặt độc lập theo từng tài khoản.
"""

import sqlite3
import pandas as pd
import numpy as np
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import settings

class TransactionImporter:
    """Bộ máy Nạp & Tái hiện Sổ kế toán Quỹ đầu tư AI"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.SQLITE_DB_PATH
        self.schema_path = settings.DATABASE_DIR / "schema.sql"
        self.csv_path = settings.DATA_DIR / "historical_transactions.csv"
        self.fees_path = settings.DATA_DIR / "broker_fees.csv"

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def reset_and_init_db(self):
        """Khởi tạo lại cấu trúc bảng từ schema.sql"""
        with self.get_connection() as conn:
            # Xóa các bảng cũ nếu cấu trúc schema đã được nâng cấp
            conn.executescript("""
                DROP TABLE IF EXISTS portfolio;
                DROP TABLE IF EXISTS transactions;
                DROP TABLE IF EXISTS account_cash_balance;
                DROP TABLE IF EXISTS broker_accounts;
                DROP TABLE IF EXISTS nav_daily;
                DROP TABLE IF EXISTS order_history;
                DROP TABLE IF EXISTS corporate_actions;
                DROP TABLE IF EXISTS decision_memos;
                DROP TABLE IF EXISTS system_settings;
            """)
            with open(self.schema_path, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            conn.commit()

    def load_broker_accounts(self):
        """Khởi tạo danh sách các tài khoản CTCK và biểu phí"""
        accounts_meta = [
            ("0001716319", "VNDIRECT / TCBS", 0.00097, "ACTIVE", "2023-09-06", "Tài khoản giao dịch chính hiện tại"),
            ("009C105992", "VCBS", 0.0015, "INACTIVE", "2016-06-16", "Tài khoản VCBS giai đoạn 2016-2024"),
            ("127008", "VPS", 0.001, "INACTIVE", "2021-04-29", "Tài khoản VPS giai đoạn 2021-2023"),
            ("123C006116", "DNSE / KAFI", 0.001, "CLOSED", "2025-02-05", "Tài khoản phụ đã tất toán")
        ]
        with self.get_connection() as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO broker_accounts (account_id, broker_name, fee_rate, status, opened_date, notes)
                VALUES (?, ?, ?, ?, ?, ?);
            """, accounts_meta)
            conn.commit()

    def run_import(self) -> Dict[str, Any]:
        """Thực thi replay toàn bộ 1.710 giao dịch và cập nhật database"""
        self.reset_and_init_db()
        self.load_broker_accounts()

        if not self.csv_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file giao dịch tại {self.csv_path}")

        df = pd.read_csv(self.csv_path)
        print(f"[TransactionImporter] Đọc được {len(df)} dòng giao dịch.")

        # Chuẩn hóa cột ngày tháng và sắp xếp theo trình tự thời gian
        # Giữ thứ tự gốc trong file khi cùng ngày (stable sort)
        df['orig_idx'] = df.index
        df['parsed_trade_date'] = pd.to_datetime(df['Date of Trade'])
        df = df.sort_values(by=['parsed_trade_date', 'orig_idx']).reset_index(drop=True)

        # Trạng thái theo dõi vị thế độc lập per (account, symbol)
        # positions[(acc, sym)] = {'qty': float, 'total_cost': float, 'avg_price': float, 'first_date': str}
        positions = {}
        # cash_balances[acc] = float
        cash_balances = {
            "0001716319": 0.0,
            "009C105992": 0.0,
            "127008": 0.0,
            "123C006116": 0.0
        }

        # Lưu lịch sử giá gần nhất của từng cổ phiếu để tính Mark-to-Market NAV
        latest_prices = {}

        transactions_to_insert = []
        nav_daily_records = {} # trade_date -> snapshot
        cumulative_realized_pnl = 0.0

        tax_effective_date = pd.to_datetime('2020-12-05')

        SUSPENDED_TICKERS = {
            "FLC": pd.to_datetime("2023-02-20")
        }

        for idx, row in df.iterrows():
            trade_date_dt = row['parsed_trade_date']
            trade_date = trade_date_dt.strftime('%Y-%m-%d')
            money_date = str(row['Date of Money'])[:10] if pd.notna(row['Date of Money']) else None
            symbol_date = str(row['Date of Symbol'])[:10] if pd.notna(row['Date of Symbol']) else None
            acc = str(row['Account']).strip()
            t = str(row['Type']).strip()
            sym = str(row['Symbol']).strip() if pd.notna(row['Symbol']) and str(row['Symbol']).strip() != 'nan' else None
            
            qty = float(row['Quantity']) if pd.notna(row['Quantity']) else 0.0
            cost = float(row['Cost']) if pd.notna(row['Cost']) else 0.0
            fee = float(row['Fee']) if pd.notna(row['Fee']) else 0.0
            tax = float(row['Tax']) if pd.notna(row['Tax']) else 0.0
            amt = float(row['Amount']) if pd.notna(row['Amount']) else 0.0
            tot_amt = float(row['Total Amount']) if pd.notna(row['Total Amount']) else 0.0
            comment = str(row['Comment']) if pd.notna(row['Comment']) else None

            # Cập nhật số dư tiền mặt tài khoản
            if acc not in cash_balances:
                cash_balances[acc] = 0.0
            cash_balances[acc] += tot_amt

            calc_avg_price = None
            calc_profit = None
            calc_profit_pct = None

            if sym:
                pos_key = (acc, sym)
                if pos_key not in positions:
                    positions[pos_key] = {'qty': 0.0, 'total_cost': 0.0, 'avg_price': 0.0, 'first_date': trade_date}
                pos = positions[pos_key]

                if cost > 0:
                    latest_prices[sym] = cost

                # 1. NGHIỆP VỤ MUA (Khớp thường, Lô lẻ, Quyền mua)
                if t in ['Mua', 'Mua lô lẻ', 'Quyền mua']:
                    new_qty = pos['qty'] + qty
                    buy_cost = (qty * cost) + fee
                    new_total_cost = pos['total_cost'] + buy_cost
                    calc_avg_price = new_total_cost / new_qty if new_qty > 0 else 0.0
                    
                    pos['qty'] = new_qty
                    pos['total_cost'] = new_total_cost
                    pos['avg_price'] = calc_avg_price
                    if pos['qty'] == qty:
                        pos['first_date'] = trade_date

                # 2. NGHIỆP VỤ BÁN (Khớp thường, Lô lẻ)
                elif t in ['Bán', 'Bán lô lẻ']:
                    sell_qty = abs(qty)
                    cost_basis_sold = sell_qty * pos['avg_price']
                    net_proceeds = tot_amt
                    
                    calc_profit = net_proceeds - cost_basis_sold
                    calc_profit_pct = calc_profit / cost_basis_sold if cost_basis_sold > 0 else 0.0
                    cumulative_realized_pnl += calc_profit

                    new_qty = pos['qty'] - sell_qty
                    if abs(new_qty) < 1e-4:
                        pos['qty'] = 0.0
                        pos['total_cost'] = 0.0
                        pos['avg_price'] = 0.0
                    else:
                        pos['qty'] = new_qty
                        pos['total_cost'] = max(0.0, pos['total_cost'] - cost_basis_sold)
                    
                    calc_avg_price = pos['avg_price']

                # 3. CỔ TỨC BẰNG CỔ PHIẾU / CỔ PHIẾU THƯỞNG
                elif t == 'Cổ tức bằng cổ phiếu':
                    # Kiểm tra hiệu lực Nghị định 126/2020: Thuế 5% trên mệnh giá 10k từ 05/12/2020
                    tax_5pct = (qty * 10000.0 * 0.05) if trade_date_dt >= tax_effective_date else 0.0
                    
                    new_qty = pos['qty'] + qty
                    new_total_cost = pos['total_cost'] + tax_5pct
                    calc_avg_price = new_total_cost / new_qty if new_qty > 0 else 0.0

                    pos['qty'] = new_qty
                    pos['total_cost'] = new_total_cost
                    pos['avg_price'] = calc_avg_price

                # 4. CỔ TỨC BẰNG TIỀN MẶT
                elif t == 'Cổ tức bằng tiền':
                    div_cash = cost if cost > 0 else tot_amt
                    new_total_cost = max(0.0, pos['total_cost'] - div_cash)
                    calc_avg_price = new_total_cost / pos['qty'] if pos['qty'] > 0 else 0.0

                    pos['total_cost'] = new_total_cost
                    pos['avg_price'] = calc_avg_price

            transactions_to_insert.append((
                trade_date, money_date, symbol_date, acc, t, sym,
                qty, cost, fee, tax, amt, tot_amt,
                calc_avg_price, calc_profit, calc_profit_pct, comment
            ))

            # Tính NAV ngày
            # Tổng giá trị cổ phiếu nắm giữ trên mọi tài khoản
            # Lưu ý: Cổ phiếu bị đình chỉ giao dịch/hủy niêm yết (treo sàn như FLC) được định giá 0đ
            current_stock_val = 0.0
            current_unrealized_pnl = 0.0
            for (p_acc, p_sym), p_state in positions.items():
                if p_state['qty'] > 0:
                    if p_sym in SUSPENDED_TICKERS and trade_date_dt >= SUSPENDED_TICKERS[p_sym]:
                        px = 0.0
                    else:
                        px = latest_prices.get(p_sym, p_state['avg_price'])
                    mv = p_state['qty'] * px
                    current_stock_val += mv
                    current_unrealized_pnl += (mv - p_state['total_cost'])

            total_cash = sum(cash_balances.values())
            total_nav = total_cash + current_stock_val

            nav_daily_records[trade_date] = {
                'trade_date': trade_date,
                'total_nav': total_nav,
                'cash_balance': total_cash,
                'stock_value': current_stock_val,
                'cumulative_pnl': cumulative_realized_pnl + current_unrealized_pnl,
                'realized_pnl': cumulative_realized_pnl,
                'unrealized_pnl': current_unrealized_pnl,
                'notes': f"Replay kế toán từ GD số {idx+1}: {t} {sym or ''}"
            }

        # NẠP VÀO DATABASE
        with self.get_connection() as conn:
            # 1. Nạp bảng transactions
            conn.executemany("""
                INSERT INTO transactions (
                    trade_date, money_date, symbol_date, account, type, symbol,
                    quantity, cost, fee, tax, amount, total_amount,
                    avg_price, profit, profit_pct, comment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, transactions_to_insert)

            # 2. Nạp số dư tiền mặt account_cash_balance
            for acc_id, bal in cash_balances.items():
                conn.execute("""
                    INSERT OR REPLACE INTO account_cash_balance (account_id, cash_balance, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP);
                """, (acc_id, bal))

            # 3. Nạp danh mục cổ phiếu mở (portfolio)
            portfolio_rows = []
            total_active_stock_val = 0.0
            for (acc_id, ticker), pos in positions.items():
                if pos['qty'] > 0.01:
                    is_suspended = (ticker in SUSPENDED_TICKERS)
                    if is_suspended:
                        cur_px = 0.0
                        mkt_val = 0.0
                        unrealized = -pos['total_cost']
                        unrealized_pct = -100.0
                    else:
                        cur_px = latest_prices.get(ticker, pos['avg_price'])
                        mkt_val = pos['qty'] * cur_px
                        unrealized = mkt_val - pos['total_cost']
                        unrealized_pct = (unrealized / pos['total_cost']) * 100.0 if pos['total_cost'] > 0 else 0.0
                    
                    total_active_stock_val += mkt_val
                    portfolio_rows.append((
                        acc_id, ticker, pos['qty'], pos['avg_price'], cur_px, mkt_val,
                        unrealized, unrealized_pct, 0.0, pos['first_date']
                    ))

            # Cập nhật tỷ trọng weight_pct
            for row in portfolio_rows:
                acc_id, ticker, q, avg_p, cur_p, mkt_val, un_pnl, un_pct, _, f_date = row
                tot_nav_active = total_cash + total_active_stock_val
                w_pct = (mkt_val / tot_nav_active) * 100.0 if tot_nav_active > 0 else 0.0
                conn.execute("""
                    INSERT OR REPLACE INTO portfolio (
                        account, ticker, strategy_book, quantity, avg_buy_price, current_price, market_value,
                        unrealized_pnl, unrealized_pnl_pct, weight_pct, first_bought_date, updated_at
                    ) VALUES (?, ?, 'QUANT', ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """, (acc_id, ticker, q, avg_p, cur_p, mkt_val, un_pnl, un_pct, w_pct, f_date))

            # 4. Nạp lịch sử NAV hàng ngày (nav_daily)
            sorted_dates = sorted(nav_daily_records.keys())
            prev_nav = None
            nav_inserts = []
            for d in sorted_dates:
                rec = nav_daily_records[d]
                daily_pnl = (rec['total_nav'] - prev_nav) if prev_nav is not None else 0.0
                daily_pnl_pct = (daily_pnl / prev_nav * 100.0) if prev_nav and prev_nav > 0 else 0.0
                prev_nav = rec['total_nav']
                nav_inserts.append((
                    rec['trade_date'], rec['total_nav'], rec['cash_balance'], rec['stock_value'],
                    0.0, rec['total_nav'], # core_nav, quant_nav
                    daily_pnl, daily_pnl_pct, rec['cumulative_pnl'], rec['realized_pnl'], rec['unrealized_pnl'],
                    rec['notes']
                ))

            conn.executemany("""
                INSERT OR REPLACE INTO nav_daily (
                    trade_date, total_nav, cash_balance, stock_value,
                    core_nav, quant_nav,
                    daily_pnl, daily_pnl_pct, cumulative_pnl, realized_pnl, unrealized_pnl,
                    notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, nav_inserts)

            # Cập nhật cài đặt hệ thống
            latest_nav = nav_daily_records[sorted_dates[-1]]['total_nav']
            conn.execute("""
                INSERT OR REPLACE INTO system_settings (key, value, description, updated_at)
                VALUES 
                    ('active_account', '0001716319', 'Tài khoản giao dịch chính đang kích hoạt', CURRENT_TIMESTAMP),
                    ('last_transaction_date', ?, 'Ngày giao dịch gần nhất được nạp vào sổ', CURRENT_TIMESTAMP),
                    ('total_transactions', ?, 'Tổng số lượng giao dịch lịch sử trong sổ', CURRENT_TIMESTAMP);
            """, (sorted_dates[-1], str(len(transactions_to_insert))))

            conn.commit()

        print(f"[TransactionImporter] Hoàn tất nạp {len(transactions_to_insert)} giao dịch thành công!")
        return {
            "total_transactions": len(transactions_to_insert),
            "cash_balances": cash_balances,
            "active_portfolio_count": len([p for p in positions.values() if p['qty'] > 0.01]),
            "latest_nav": nav_daily_records[sorted_dates[-1]]['total_nav']
        }

if __name__ == "__main__":
    importer = TransactionImporter()
    res = importer.run_import()
    print("Kết quả Replay Kế toán:", res)

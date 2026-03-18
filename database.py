# =============================================================================
# database.py — ALL DATABASE LOGIC IN ONE PLACE
# =============================================================================
# TO ADD A NEW TABLE:  add CREATE TABLE in setup_database()
# TO ADD A NEW QUERY:  add a function at the bottom of this file
# =============================================================================

import sqlite3
from datetime import datetime
from config import DB_PATH


def get_connection():
    """Returns a new SQLite connection. Always close after use."""
    return sqlite3.connect(DB_PATH)


def setup_database():
    """Creates all tables if they don't exist. Safe to call on every startup."""
    conn = get_connection()
    c = conn.cursor()

    # Markets scanned by the bot
    c.execute("""CREATE TABLE IF NOT EXISTS markets (
        id TEXT PRIMARY KEY, title TEXT, platform TEXT,
        yes_price REAL, no_price REAL, volume REAL,
        days_to_expiry INTEGER, flagged INTEGER DEFAULT 0, last_scanned TEXT)""")

    # AI predictions per market
    c.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, market_id TEXT,
        our_probability REAL, market_price REAL, edge REAL,
        reasoning TEXT, created_at TEXT)""")

    # Every trade (paper or real)
    c.execute("""CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT, market_id TEXT, market_title TEXT,
        direction TEXT, entry_price REAL, size REAL, kelly_size REAL,
        bankroll_at_entry REAL, status TEXT DEFAULT 'open', outcome TEXT,
        exit_price REAL, pnl REAL, notes TEXT, tags TEXT,
        opened_at TEXT, closed_at TEXT)""")

    # ── Watchlist holdings — CommSec-style position tracking ─────────────────
    # Each row = one market you're watching or holding a position in.
    # bought_price + units enables unrealised P&L calculation.
    c.execute("""CREATE TABLE IF NOT EXISTS watchlist (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        title         TEXT NOT NULL,
        platform      TEXT DEFAULT 'manual',
        category      TEXT DEFAULT 'General',
        -- Current market data
        current_price REAL DEFAULT 0.5,
        prev_price    REAL,
        -- My position (null = just watching, not holding)
        direction     TEXT,
        bought_price  REAL,
        units         INTEGER,
        total_cost    REAL,
        -- Metadata
        notes         TEXT,
        status        TEXT DEFAULT 'watching',
        added_at      TEXT,
        updated_at    TEXT)""")

    # Daily AI reports
    c.execute("""CREATE TABLE IF NOT EXISTS daily_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT UNIQUE,
        report TEXT, created_at TEXT)""")

    conn.commit()
    conn.close()
    print("✓ Database ready")


# ── MARKET FUNCTIONS ─────────────────────────────────────────────────────────

def save_market(market: dict):
    conn = get_connection(); c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO markets
        (id,title,platform,yes_price,no_price,volume,days_to_expiry,flagged,last_scanned)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (market["id"],market["title"],market["platform"],
         market["yes_price"],market["no_price"],market["volume"],
         market["days_to_expiry"],market.get("flagged",0),datetime.now().isoformat()))
    conn.commit(); conn.close()


def get_markets(limit=100):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT id,title,platform,yes_price,no_price,volume,days_to_expiry,flagged,last_scanned
        FROM markets ORDER BY last_scanned DESC LIMIT ?""",(limit,))
    rows = c.fetchall(); conn.close()
    keys = ["id","title","platform","yes_price","no_price","volume","days_to_expiry","flagged","last_scanned"]
    return [dict(zip(keys,r)) for r in rows]


# ── PREDICTION FUNCTIONS ─────────────────────────────────────────────────────

def save_prediction(prediction: dict):
    conn = get_connection(); c = conn.cursor()
    c.execute("""INSERT INTO predictions (market_id,our_probability,market_price,edge,reasoning,created_at)
        VALUES (?,?,?,?,?,?)""",
        (prediction["market_id"],prediction["our_probability"],prediction["market_price"],
         prediction["edge"],prediction["reasoning"],datetime.now().isoformat()))
    conn.commit(); conn.close()


def get_predictions(limit=50):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT p.id,p.market_id,m.title,p.our_probability,p.market_price,p.edge,p.reasoning,p.created_at
        FROM predictions p LEFT JOIN markets m ON p.market_id=m.id
        ORDER BY p.created_at DESC LIMIT ?""",(limit,))
    rows = c.fetchall(); conn.close()
    keys = ["id","market_id","title","our_probability","market_price","edge","reasoning","created_at"]
    return [dict(zip(keys,r)) for r in rows]


# ── TRADE FUNCTIONS ──────────────────────────────────────────────────────────

def save_trade(trade: dict):
    conn = get_connection(); c = conn.cursor()
    c.execute("""INSERT INTO trades
        (market_id,market_title,direction,entry_price,size,kelly_size,bankroll_at_entry,notes,opened_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (trade.get("market_id","manual"),trade.get("market_title","Unknown"),
         trade.get("direction","YES"),trade.get("entry_price",0.5),
         trade.get("size",0),trade.get("kelly_size",0),
         trade.get("bankroll_at_entry",1000),trade.get("notes",""),datetime.now().isoformat()))
    conn.commit(); conn.close()


def close_trade(trade_id: int, outcome: str, pnl: float):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE trades SET status='closed',outcome=?,pnl=?,closed_at=? WHERE id=?",
              (outcome,pnl,datetime.now().isoformat(),trade_id))
    conn.commit(); conn.close()


def update_trade_notes(trade_id: int, notes: str, tags: str):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE trades SET notes=?,tags=? WHERE id=?",(notes,tags,trade_id))
    conn.commit(); conn.close()


def get_trades(limit=200):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT id,market_id,market_title,direction,entry_price,size,kelly_size,
        bankroll_at_entry,status,outcome,pnl,notes,tags,opened_at,closed_at
        FROM trades ORDER BY opened_at DESC LIMIT ?""",(limit,))
    rows = c.fetchall(); conn.close()
    keys = ["id","market_id","market_title","direction","entry_price","size","kelly_size",
            "bankroll_at_entry","status","outcome","pnl","notes","tags","opened_at","closed_at"]
    return [dict(zip(keys,r)) for r in rows]


def get_stats():
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT COUNT(*),
        SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END),
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END),
        ROUND(SUM(COALESCE(pnl,0)),2),
        COUNT(CASE WHEN status='open' THEN 1 END) FROM trades""")
    row = c.fetchone()
    total,wins,losses,pnl,open_pos = row
    wins=wins or 0; losses=losses or 0; pnl=pnl or 0.0
    c.execute("SELECT COUNT(*) FROM markets"); mkt=c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM predictions"); pred=c.fetchone()[0] or 0
    conn.close()
    return {"total_trades":total or 0,"wins":wins,"losses":losses,"pnl":pnl,
            "open_positions":open_pos or 0,"win_rate":round(wins/total*100,1) if total else 0,
            "markets_scanned":mkt,"predictions_run":pred}


# ── WATCHLIST FUNCTIONS ──────────────────────────────────────────────────────

def add_watchlist_item(item: dict) -> int:
    """Adds a holding/watchlist entry. Returns new row id."""
    conn = get_connection(); c = conn.cursor()
    bp = item.get("bought_price")
    u  = item.get("units")
    tc = round(float(bp)*int(u),4) if bp and u else None
    c.execute("""INSERT INTO watchlist
        (title,platform,category,current_price,prev_price,direction,bought_price,units,total_cost,notes,status,added_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (item.get("title",""), item.get("platform","manual"), item.get("category","General"),
         item.get("current_price",0.5), item.get("current_price",0.5),
         item.get("direction"), bp, u, tc, item.get("notes",""),
         "holding" if bp and u else "watching",
         datetime.now().isoformat(), datetime.now().isoformat()))
    new_id = c.lastrowid
    conn.commit(); conn.close()
    return new_id


def get_watchlist() -> list:
    """
    Returns all watchlist items with calculated fields added:
      unrealised_pnl  — profit/loss on current position
      current_value   — current market value of position
      pnl_pct         — unrealised P&L as % of total cost
      price_change     — movement since item was added
      price_change_pct — % movement since added
    """
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT id,title,platform,category,current_price,prev_price,
        direction,bought_price,units,total_cost,notes,status,added_at,updated_at
        FROM watchlist ORDER BY added_at DESC""")
    rows = c.fetchall(); conn.close()
    keys = ["id","title","platform","category","current_price","prev_price",
            "direction","bought_price","units","total_cost","notes","status","added_at","updated_at"]
    items = []
    for row in rows:
        item = dict(zip(keys, row))
        cp = item["current_price"] or 0.5
        bp = item["bought_price"]
        pp = item["prev_price"] or cp
        u  = item["units"] or 0

        if bp and u:
            # YES position gains when price rises; NO position gains when price falls
            if item.get("direction") == "NO":
                item["unrealised_pnl"] = round((float(bp)-cp)*u, 4)
                item["current_value"]  = round((1-cp)*u, 4)
            else:
                item["unrealised_pnl"] = round((cp-float(bp))*u, 4)
                item["current_value"]  = round(cp*u, 4)
            tc = item["total_cost"] or 1
            item["pnl_pct"] = round(item["unrealised_pnl"]/tc*100, 2)
        else:
            item["unrealised_pnl"] = None
            item["current_value"]  = None
            item["pnl_pct"]        = None

        item["price_change"]     = round(cp-pp, 4)
        item["price_change_pct"] = round((cp-pp)/pp*100, 2) if pp else 0
        items.append(item)
    return items


def update_watchlist_price(item_id: int, new_price: float):
    """Updates only the current price of a watchlist item."""
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE watchlist SET current_price=?,updated_at=? WHERE id=?",
              (new_price, datetime.now().isoformat(), item_id))
    conn.commit(); conn.close()


def update_watchlist_item(item_id: int, updates: dict):
    """Full update of a watchlist item's fields."""
    conn = get_connection(); c = conn.cursor()
    bp = updates.get("bought_price")
    u  = updates.get("units")
    tc = round(float(bp)*int(u),4) if bp and u else None
    c.execute("""UPDATE watchlist SET title=?,category=?,current_price=?,direction=?,
        bought_price=?,units=?,total_cost=?,notes=?,status=?,updated_at=? WHERE id=?""",
        (updates.get("title"), updates.get("category","General"),
         updates.get("current_price"), updates.get("direction"),
         bp, u, tc, updates.get("notes",""), updates.get("status","watching"),
         datetime.now().isoformat(), item_id))
    conn.commit(); conn.close()


def remove_watchlist_item(item_id: int):
    conn = get_connection(); c = conn.cursor()
    c.execute("DELETE FROM watchlist WHERE id=?",(item_id,))
    conn.commit(); conn.close()


def get_watchlist_summary() -> dict:
    """Portfolio-level summary across all holdings."""
    items    = get_watchlist()
    holdings = [i for i in items if i["bought_price"] and i["units"]]
    total_invested = sum(i["total_cost"] or 0 for i in holdings)
    total_value    = sum(i["current_value"] or 0 for i in holdings)
    total_pnl      = sum(i["unrealised_pnl"] or 0 for i in holdings)
    best  = max(holdings, key=lambda x: x["unrealised_pnl"] or 0) if holdings else None
    worst = min(holdings, key=lambda x: x["unrealised_pnl"] or 0) if holdings else None
    return {
        "total_holdings":       len(items),
        "active_holdings":      len(holdings),
        "watching_only":        len(items)-len(holdings),
        "total_invested":       round(total_invested,2),
        "total_value":          round(total_value,2),
        "total_unrealised_pnl": round(total_pnl,2),
        "best_performer":       best["title"] if best else None,
        "worst_performer":      worst["title"] if worst else None,
    }


# ── DAILY REPORT FUNCTIONS ───────────────────────────────────────────────────

def save_daily_report(report_text: str):
    today = datetime.now().strftime("%Y-%m-%d")
    conn  = get_connection(); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO daily_reports (date,report,created_at) VALUES (?,?,?)",
              (today, report_text, datetime.now().isoformat()))
    conn.commit(); conn.close()


def get_latest_report():
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT date,report,created_at FROM daily_reports ORDER BY date DESC LIMIT 1")
    row = c.fetchone(); conn.close()
    return {"date":row[0],"report":row[1],"created_at":row[2]} if row else None


if __name__ == "__main__":
    setup_database()
    print("Database initialised at:", DB_PATH)
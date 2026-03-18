# =============================================================================
# api/routes.py — ALL FLASK ROUTES, GROUPED BY FEATURE
# =============================================================================
# TO ADD A NEW ENDPOINT:
#   1. Find the right section below
#   2. Add your @bp.route(...) function
#   3. Add @login_required if it should be protected
#   4. Add the matching fetch call in gui.html
# =============================================================================

import os, csv, io, threading
from datetime import datetime
from flask import Blueprint, jsonify, request, session, redirect, Response

from api.auth  import login_required, check_password, set_password, is_password_set, get_login_page
from database  import (get_stats, get_markets, get_predictions, get_trades, save_trade,
                       close_trade, update_trade_notes,
                       get_watchlist, get_watchlist_summary, add_watchlist_item,
                       update_watchlist_item, update_watchlist_price, remove_watchlist_item,
                       get_latest_report)
from bot.pipeline import run_pipeline, get_log, is_running
from bot.advisor  import generate_daily_report, get_holding_advice, compare_holdings, chat_with_advisor
from config import DB_PATH

audit_log = []
bp = Blueprint("routes", __name__)


def record_audit(method, path, ip):
    audit_log.append({"time": datetime.now().strftime("%H:%M:%S"), "method": method, "path": path, "ip": ip})
    if len(audit_log) > 100: audit_log.pop(0)


# =============================================================================
# AUTH
# =============================================================================

@bp.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if check_password(request.form.get("password","")):
            session["logged_in"] = True
            return redirect("/")
        return get_login_page(error=True)
    return get_login_page()

@bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =============================================================================
# STATS
# =============================================================================

@bp.route("/api/stats")
@login_required
def api_stats():
    try:
        s = get_stats()
        s["bot_running"]  = is_running()
        s["kill_switch"]  = os.path.exists("STOP")
        s["password_set"] = is_password_set()
        return jsonify(s)
    except Exception as e:
        return jsonify({"error": str(e)})


# =============================================================================
# MARKETS
# =============================================================================

@bp.route("/api/markets")
@login_required
def api_markets():
    try: return jsonify(get_markets())
    except Exception as e: return jsonify({"error": str(e)})


# =============================================================================
# PREDICTIONS
# =============================================================================

@bp.route("/api/predictions")
@login_required
def api_predictions():
    try: return jsonify(get_predictions())
    except Exception as e: return jsonify({"error": str(e)})


# =============================================================================
# TRADES
# =============================================================================

@bp.route("/api/trades")
@login_required
def api_trades():
    try: return jsonify(get_trades())
    except Exception as e: return jsonify({"error": str(e)})


@bp.route("/api/trades/manual", methods=["POST"])
@login_required
def api_manual_trade():
    record_audit("POST", request.path, request.remote_addr)
    d = request.json or {}
    try:
        save_trade({"market_id":"manual","market_title":d.get("title","Manual"),
                    "direction":d.get("direction","YES"),
                    "entry_price":float(d.get("entry_price",0.5)),
                    "size":float(d.get("size",10)),
                    "kelly_size":float(d.get("size",10)),
                    "bankroll_at_entry":float(d.get("bankroll",1000)),
                    "notes":d.get("notes","")})
        return jsonify({"status":"ok"})
    except Exception as e: return jsonify({"error": str(e)})


@bp.route("/api/trades/<int:tid>/close", methods=["POST"])
@login_required
def api_close_trade(tid):
    record_audit("POST", request.path, request.remote_addr)
    d = request.json or {}
    try:
        close_trade(tid, d.get("outcome","win"), float(d.get("pnl",0)))
        return jsonify({"status":"ok"})
    except Exception as e: return jsonify({"error": str(e)})


@bp.route("/api/trades/<int:tid>/notes", methods=["POST"])
@login_required
def api_trade_notes(tid):
    record_audit("POST", request.path, request.remote_addr)
    d = request.json or {}
    try:
        update_trade_notes(tid, d.get("notes",""), d.get("tags",""))
        return jsonify({"status":"ok"})
    except Exception as e: return jsonify({"error": str(e)})


@bp.route("/api/trades/export")
@login_required
def api_export_trades():
    try:
        trades = get_trades(10000)
        out    = io.StringIO()
        if trades:
            w = csv.DictWriter(out, fieldnames=trades[0].keys())
            w.writeheader(); w.writerows(trades)
        return Response(out.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition":"attachment;filename=trades.csv"})
    except Exception as e: return jsonify({"error": str(e)})


# =============================================================================
# WATCHLIST — CommSec-style holdings tracker
# =============================================================================

@bp.route("/api/watchlist")
@login_required
def api_watchlist():
    """Returns all watchlist items with calculated P&L fields."""
    try: return jsonify(get_watchlist())
    except Exception as e: return jsonify({"error": str(e)})


@bp.route("/api/watchlist/summary")
@login_required
def api_watchlist_summary():
    """Returns portfolio-level summary (total invested, total P&L, etc.)."""
    try: return jsonify(get_watchlist_summary())
    except Exception as e: return jsonify({"error": str(e)})


@bp.route("/api/watchlist", methods=["POST"])
@login_required
def api_add_watchlist():
    """Adds a new holding or watchlist entry."""
    record_audit("POST", request.path, request.remote_addr)
    d = request.json or {}
    try:
        bp_val = float(d["bought_price"])/100 if d.get("bought_price") else None
        new_id = add_watchlist_item({
            "title":         d.get("title",""),
            "platform":      d.get("platform","manual"),
            "category":      d.get("category","General"),
            "current_price": float(d.get("current_price",50))/100,
            "direction":     d.get("direction"),
            "bought_price":  bp_val,
            "units":         int(d["units"]) if d.get("units") else None,
            "notes":         d.get("notes",""),
        })
        return jsonify({"status":"ok","id":new_id})
    except Exception as e: return jsonify({"error": str(e)})


@bp.route("/api/watchlist/<int:iid>", methods=["PUT"])
@login_required
def api_update_watchlist(iid):
    """Full update of a watchlist item."""
    record_audit("POST", request.path, request.remote_addr)
    d = request.json or {}
    try:
        bp_val = float(d["bought_price"])/100 if d.get("bought_price") else None
        update_watchlist_item(iid, {
            "title":         d.get("title"),
            "category":      d.get("category","General"),
            "current_price": float(d.get("current_price",50))/100,
            "direction":     d.get("direction"),
            "bought_price":  bp_val,
            "units":         int(d["units"]) if d.get("units") else None,
            "notes":         d.get("notes",""),
            "status":        d.get("status","watching"),
        })
        return jsonify({"status":"ok"})
    except Exception as e: return jsonify({"error": str(e)})


@bp.route("/api/watchlist/<int:iid>/price", methods=["POST"])
@login_required
def api_update_price(iid):
    """Updates just the current price of a holding (quick refresh)."""
    record_audit("POST", request.path, request.remote_addr)
    d = request.json or {}
    try:
        update_watchlist_price(iid, float(d.get("price",50))/100)
        return jsonify({"status":"ok"})
    except Exception as e: return jsonify({"error": str(e)})


@bp.route("/api/watchlist/<int:iid>", methods=["DELETE"])
@login_required
def api_delete_watchlist(iid):
    record_audit("DELETE", request.path, request.remote_addr)
    try: remove_watchlist_item(iid); return jsonify({"status":"ok"})
    except Exception as e: return jsonify({"error": str(e)})


@bp.route("/api/watchlist/<int:iid>/advice")
@login_required
def api_holding_advice(iid):
    """AI buy/sell/hold advice on a specific holding."""
    try: return jsonify({"advice": get_holding_advice(iid)})
    except Exception as e: return jsonify({"error": str(e)})


@bp.route("/api/watchlist/compare", methods=["POST"])
@login_required
def api_compare():
    """AI comparison of two watchlist items."""
    d = request.json or {}
    try: return jsonify({"comparison": compare_holdings(d.get("id_a"), d.get("id_b"))})
    except Exception as e: return jsonify({"error": str(e)})


# =============================================================================
# AI ADVISOR
# =============================================================================

@bp.route("/api/advisor/report")
@login_required
def api_report():
    try:
        r = get_latest_report()
        if not r: r = {"report": "No report yet — click Generate Report.", "date":""}
        return jsonify(r)
    except Exception as e: return jsonify({"error": str(e)})


@bp.route("/api/advisor/report/generate", methods=["POST"])
@login_required
def api_generate_report():
    record_audit("POST", request.path, request.remote_addr)
    try:
        text = generate_daily_report()
        return jsonify({"report": text, "date": datetime.now().strftime("%Y-%m-%d")})
    except Exception as e: return jsonify({"error": str(e)})


@bp.route("/api/advisor/chat", methods=["POST"])
@login_required
def api_chat():
    record_audit("POST", request.path, request.remote_addr)
    d = request.json or {}
    msg = d.get("message","").strip()
    if not msg: return jsonify({"error":"No message"})
    try: return jsonify({"reply": chat_with_advisor(msg)})
    except Exception as e: return jsonify({"error": str(e)})


# =============================================================================
# BOT CONTROLS
# =============================================================================

@bp.route("/api/scan", methods=["POST"])
@login_required
def api_scan():
    record_audit("POST", request.path, request.remote_addr)
    if is_running(): return jsonify({"status":"already running"})
    threading.Thread(target=lambda: run_pipeline(bankroll=1000.0, paper_only=True), daemon=True).start()
    return jsonify({"status":"scan started"})


@bp.route("/api/logs")
@login_required
def api_logs():
    return jsonify({"logs": get_log()})


@bp.route("/api/killswitch", methods=["POST"])
@login_required
def api_killswitch():
    record_audit("POST", request.path, request.remote_addr)
    d = request.json or {}
    if d.get("activate", True): open("STOP","w").close()
    elif os.path.exists("STOP"): os.remove("STOP")
    return jsonify({"status":"ok","active": os.path.exists("STOP")})


# =============================================================================
# SECURITY
# =============================================================================

@bp.route("/api/security/status")
@login_required
def api_security_status():
    return jsonify({"password_set": is_password_set(), "kill_switch": os.path.exists("STOP"),
                    "db_exists": os.path.exists(DB_PATH), "logged_in": bool(session.get("logged_in"))})


@bp.route("/api/security/set-password", methods=["POST"])
@login_required
def api_set_password():
    record_audit("POST", request.path, request.remote_addr)
    d = request.json or {}
    if set_password(d.get("password","")): return jsonify({"status":"ok"})
    return jsonify({"error":"Password must be at least 6 characters"})


@bp.route("/api/security/audit-log")
@login_required
def api_audit_log():
    return jsonify(list(reversed(audit_log[-30:])))


# =============================================================================
# LIVE PRICE ENDPOINTS (added for dual-platform live feed)
# =============================================================================

from bot.live_prices import get_live_markets, refresh_watchlist_prices, get_market_price

@bp.route("/api/live/markets")
@login_required
def api_live_markets():
    """
    Returns live markets from both Polymarket (no auth) and Kalshi (needs key).
    Polymarket data always works. Kalshi requires API key in config.py.
    Cached for 60 seconds to avoid rate limits.
    """
    try:
        data = get_live_markets(use_cache=True)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)})


@bp.route("/api/live/markets/refresh")
@login_required
def api_live_markets_refresh():
    """Forces a fresh fetch, bypassing the cache."""
    try:
        data = get_live_markets(use_cache=False)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)})


@bp.route("/api/watchlist/refresh-prices", methods=["POST"])
@login_required
def api_refresh_watchlist_prices():
    """
    Auto-refreshes prices for all watchlist items by fuzzy-matching
    against live Polymarket and Kalshi data.
    Updates database for matched items and returns the update summary.
    """
    record_audit("POST", request.path, request.remote_addr)
    try:
        watchlist = get_watchlist()
        updates   = refresh_watchlist_prices(watchlist)

        # Apply updates to database
        updated_count = 0
        for item_id, data in updates.items():
            update_watchlist_price(item_id, data["new_price"])
            updated_count += 1

        return jsonify({
            "status":        "ok",
            "updated":       updated_count,
            "total_items":   len(watchlist),
            "details":       updates,
        })
    except Exception as e:
        return jsonify({"error": str(e)})


@bp.route("/api/live/price-lookup")
@login_required
def api_price_lookup():
    """Looks up the live price for a market by title query string."""
    title = request.args.get("title","")
    if not title:
        return jsonify({"error": "provide ?title=..."})
    try:
        return jsonify(get_market_price(title))
    except Exception as e:
        return jsonify({"error": str(e)})
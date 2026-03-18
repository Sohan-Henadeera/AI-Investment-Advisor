# =============================================================================
# bot/advisor.py — AI DAILY REPORTS, WATCHLIST ADVICE, CHAT
# =============================================================================
# All AI runs locally via Ollama — zero cost, zero data leaves your device.
#
# TO CHANGE REPORT STYLE: edit build_daily_report_prompt()
# TO ADD A NEW ADVICE TYPE: add a build_*_prompt() + public function
# =============================================================================

import requests
from datetime import datetime
from config import OLLAMA_MODEL, OLLAMA_URL
from database import get_stats, get_trades, get_watchlist, get_watchlist_summary, get_latest_report, save_daily_report


def ask_ollama(prompt: str, max_tokens: int = 800) -> str:
    """Sends a prompt to Ollama. Returns response text or error message."""
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.4, "num_predict": max_tokens}
        }, timeout=120)
        if r.status_code == 200:
            return r.json().get("response","").strip()
        return f"AI unavailable (status {r.status_code}). Make sure Ollama is running."
    except requests.exceptions.ConnectionError:
        return "Ollama is not running. Open a terminal and run: ollama serve"
    except Exception as e:
        return f"AI error: {e}"


# ── PROMPT BUILDERS ──────────────────────────────────────────────────────────

def build_daily_report_prompt(stats, trades, watchlist, summary) -> str:
    """Builds the daily portfolio briefing prompt."""
    open_trades = [t for t in trades if t["status"]=="open"]
    holdings    = [w for w in watchlist if w["bought_price"] and w["units"]]
    watching    = [w for w in watchlist if not w["bought_price"]]

    open_str = "\n".join([
        f"  - {t['market_title'][:45]} | {t['direction']} @ {t['entry_price']:.0%} | ${t['size']:.2f}"
        for t in open_trades[:6]]) or "  None"

    holdings_str = "\n".join([
        f"  - {w['title'][:45]} | {w['direction']} | bought @ {w['bought_price']:.0%} | "
        f"now @ {w['current_price']:.0%} | P&L: ${w['unrealised_pnl']:+.2f} ({w['pnl_pct']:+.1f}%)"
        for w in holdings[:8]]) or "  None"

    watch_str = "\n".join([
        f"  - {w['title'][:45]} | current: {w['current_price']:.0%}"
        for w in watching[:5]]) or "  None"

    return f"""You are PredBot, an AI advisor for prediction market trading. Write a clear daily briefing.

DATE: {datetime.now().strftime('%A %B %d %Y')}

PORTFOLIO STATS:
  Trades: {stats['total_trades']} | Win rate: {stats['win_rate']}% | Realised P&L: ${stats['pnl']:.2f}
  Open bot positions: {stats['open_positions']}

WATCHLIST HOLDINGS (positions I'm holding):
  Total invested: ${summary['total_invested']:.2f} | Current value: ${summary['total_value']:.2f}
  Unrealised P&L: ${summary['total_unrealised_pnl']:+.2f}
  Best: {summary['best_performer'] or 'n/a'} | Worst: {summary['worst_performer'] or 'n/a'}
{holdings_str}

BOT OPEN POSITIONS:
{open_str}

WATCHLIST (watching only, no position):
{watch_str}

Write a briefing with these 5 sections — be direct, no fluff, max 350 words:
1. PORTFOLIO HEALTH — overall status, any red flags
2. HOLDINGS REVIEW — which positions to hold, reduce, or exit
3. WATCHLIST OPPORTUNITIES — which watched markets look interesting today
4. TODAY'S FOCUS — one clear actionable recommendation
5. RISK WATCH — one specific risk to monitor today"""


def build_holding_advice_prompt(item, stats) -> str:
    """Builds a prompt for analysing a single holding."""
    has_position = item.get("bought_price") and item.get("units")
    pnl_info = ""
    if has_position:
        pnl_info = f"""
MY POSITION:
  Direction: {item['direction']} | Bought @ {item['bought_price']:.0%}
  Units: {item['units']} | Total cost: ${item['total_cost']:.2f}
  Current price: {item['current_price']:.0%} | Current value: ${item['current_value']:.2f}
  Unrealised P&L: ${item['unrealised_pnl']:+.2f} ({item['pnl_pct']:+.1f}%)
  Price change since added: {item['price_change_pct']:+.1f}%"""

    return f"""You are PredBot, an AI prediction market advisor.

MARKET: {item['title']}
Category: {item['category']}
Current market price: {item['current_price']:.0%}
Notes: {item['notes'] or 'None'}
{pnl_info}

MY PORTFOLIO: Win rate {stats['win_rate']}% | P&L ${stats['pnl']:.2f} | Open positions: {stats['open_positions']}

Give a SHORT actionable verdict (max 180 words):
VERDICT: [BUY / ADD / HOLD / REDUCE / SELL / WAIT / SKIP]
REASON: one sentence why
RISK: biggest downside risk
PRICE TARGET: where you'd expect this to settle
{"EXIT STRATEGY: when/how to close this position" if has_position else "ENTRY: suggested entry price if worth buying"}"""


def build_compare_prompt(item_a, item_b) -> str:
    """Builds a prompt comparing two watchlist items."""
    def fmt(w):
        pnl = f" | P&L: ${w['unrealised_pnl']:+.2f}" if w.get("unrealised_pnl") is not None else ""
        return f"{w['title'][:50]} | {w['current_price']:.0%}{pnl}"
    return f"""You are PredBot. Compare these two prediction market positions.

A: {fmt(item_a)}
B: {fmt(item_b)}

Which is the better hold right now and why? Max 150 words. Include:
- Which has better risk/reward
- Which you'd prioritise if you had to choose one
- Any key differences in risk"""


def build_chat_prompt(message: str, stats, trades, watchlist, summary) -> str:
    """Builds a chat prompt with full portfolio context."""
    holdings = [w for w in watchlist if w["bought_price"]]
    hold_str = ", ".join([f"{w['title'][:25]} ({w['direction']} {w['current_price']:.0%})" for w in holdings[:5]]) or "none"
    open_str = ", ".join([f"{t['market_title'][:25]}" for t in trades if t['status']=='open'][:4]) or "none"

    return f"""You are PredBot, an AI advisor for prediction market trading. Answer helpfully and concisely.

USER PORTFOLIO:
  Win rate: {stats['win_rate']}% | Realised P&L: ${stats['pnl']:.2f}
  Watchlist holdings: {hold_str}
  Bot open positions: {open_str}
  Portfolio unrealised P&L: ${summary['total_unrealised_pnl']:+.2f}

USER MESSAGE: {message}

Answer in plain English. Be direct and specific. Max 220 words."""


# ── PUBLIC FUNCTIONS ─────────────────────────────────────────────────────────

def generate_daily_report() -> str:
    """Generates, saves, and returns today's daily report."""
    print("Generating daily report...")
    stats    = get_stats()
    trades   = get_trades(50)
    watchlist= get_watchlist()
    summary  = get_watchlist_summary()
    report   = ask_ollama(build_daily_report_prompt(stats, trades, watchlist, summary), 700)
    save_daily_report(report)
    print("✓ Daily report saved")
    return report


def get_holding_advice(item_id: int) -> str:
    """Returns AI buy/sell/hold advice on a specific watchlist item."""
    item = next((w for w in get_watchlist() if w["id"]==item_id), None)
    if not item: return "Item not found."
    return ask_ollama(build_holding_advice_prompt(item, get_stats()), 400)


def compare_holdings(id_a: int, id_b: int) -> str:
    """Compares two watchlist items and recommends which to prioritise."""
    wl   = get_watchlist()
    a    = next((w for w in wl if w["id"]==id_a), None)
    b    = next((w for w in wl if w["id"]==id_b), None)
    if not a or not b: return "Could not find one or both items."
    return ask_ollama(build_compare_prompt(a, b), 300)


def chat_with_advisor(message: str) -> str:
    """Conversational AI — user can ask anything about their portfolio."""
    stats   = get_stats()
    trades  = get_trades(20)
    wl      = get_watchlist()
    summary = get_watchlist_summary()
    return ask_ollama(build_chat_prompt(message, stats, trades, wl, summary), 450)
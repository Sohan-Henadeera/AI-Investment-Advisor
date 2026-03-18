# =============================================================================
# bot/risk.py — ONE JOB: POSITION SIZING AND RISK CHECKS
# =============================================================================
# Implements the Kelly Criterion for position sizing.
# Runs safety checks before any trade is allowed through.
#
# TO ADD A NEW RISK CHECK: add an if block inside check_all_risks()
# TO CHANGE POSITION SIZING: edit kelly_size()
# =============================================================================

import os
from datetime import date
from config import (
    MIN_EDGE, KELLY_FRACTION, MAX_POSITION_PCT,
    MAX_DAILY_LOSS, MAX_POSITIONS
)
from database import get_trades


def kelly_size(probability: float, market_price: float, bankroll: float) -> float:
    """
    Calculates optimal bet size using Fractional Kelly Criterion.

    Full Kelly formula:  f* = (p*b - q) / b
    We use a fraction (KELLY_FRACTION in config.py) for safety.

    Args:
        probability:  Our estimated win probability (0.0 to 1.0)
        market_price: Current YES price (0.0 to 1.0)
        bankroll:     Total account balance in dollars

    Returns:
        Dollar amount to bet (never negative, capped at MAX_POSITION_PCT)
    """
    p = probability
    q = 1 - p
    b = (1 - market_price) / market_price  # Net odds: profit per $1 risked

    if b <= 0:
        return 0.0

    full_kelly       = (p * b - q) / b
    fractional_kelly = full_kelly * KELLY_FRACTION
    kelly_dollars    = bankroll * max(0, fractional_kelly)
    max_dollars      = bankroll * MAX_POSITION_PCT

    return round(min(kelly_dollars, max_dollars), 2)


def get_daily_loss(bankroll: float) -> float:
    """Calculates today's total losses in dollars."""
    today  = date.today().isoformat()
    trades = get_trades()
    return abs(sum(
        t["pnl"] for t in trades
        if t["pnl"] and t["pnl"] < 0 and (t["opened_at"] or "").startswith(today)
    ))


def check_all_risks(signal: dict, bankroll: float = 1000.0) -> tuple[bool, str]:
    """
    Runs every risk check before allowing a trade.
    Returns (approved: bool, reason: str).

    Add new checks here — each check should return False with a clear reason.
    """
    # ── Kill switch — check for STOP file ────────────────────────────────────
    if os.path.exists("STOP"):
        return False, "Kill switch active (STOP file exists)"

    # ── Minimum edge check ────────────────────────────────────────────────────
    edge = abs(signal.get("edge", 0))
    if edge < MIN_EDGE:
        return False, f"Edge too small: {edge:.1%} < {MIN_EDGE:.1%} minimum"

    # ── Daily loss limit ──────────────────────────────────────────────────────
    daily_loss = get_daily_loss(bankroll)
    if daily_loss >= bankroll * MAX_DAILY_LOSS:
        return False, f"Daily loss limit hit: ${daily_loss:.2f}"

    # ── Max concurrent positions ──────────────────────────────────────────────
    open_trades = [t for t in get_trades() if t["status"] == "open"]
    if len(open_trades) >= MAX_POSITIONS:
        return False, f"Too many open positions: {len(open_trades)}/{MAX_POSITIONS}"

    # ── Minimum position size (Kelly too small to bother) ─────────────────────
    size = kelly_size(signal.get("our_probability", 0.5), signal.get("market_price", 0.5), bankroll)
    if size < 1.0:
        return False, f"Kelly size too small: ${size:.2f}"

    return True, "APPROVED"


def build_position(signal: dict, bankroll: float = 1000.0) -> dict:
    """
    Builds a full position dict ready to save as a trade.
    Determines direction (YES or NO) based on which way the edge goes.
    """
    our_prob     = signal["our_probability"]
    market_price = signal["market_price"]
    edge         = signal["edge"]

    # Positive edge = buy YES, negative edge = buy NO
    if edge > 0:
        direction   = "YES"
        entry_price = market_price
    else:
        direction   = "NO"
        entry_price = signal.get("no_price", 1 - market_price)
        our_prob    = 1 - our_prob  # Flip for NO side

    size         = kelly_size(our_prob, entry_price, bankroll)
    expected_val = round(our_prob * (1 - entry_price) - (1 - our_prob) * entry_price, 4)

    return {
        "market_id":          signal["id"],
        "market_title":       signal["title"],
        "direction":          direction,
        "entry_price":        entry_price,
        "our_probability":    our_prob,
        "edge":               edge,
        "size":               size,
        "kelly_size":         size,
        "bankroll_at_entry":  bankroll,
        "expected_value":     expected_val,
    }
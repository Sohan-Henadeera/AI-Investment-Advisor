# =============================================================================
# bot/pipeline.py — ORCHESTRATES THE FULL SCAN → PREDICT → RISK CYCLE
# =============================================================================
# This is the conductor. It calls scanner, predictor, and risk in order.
# Nothing business-logic lives here — it just coordinates the other modules.
#
# TO ADD A NEW PIPELINE STEP: import it and call it in run_pipeline()
# =============================================================================

import os
from datetime import datetime
from bot.scanner   import scan_markets
from bot.predictor import run_predictions
from bot.risk      import check_all_risks, build_position
from database      import save_trade

# Global log — the GUI reads this to show live activity
pipeline_log  = []
pipeline_running = False


def log(msg: str):
    """Adds a timestamped entry to the pipeline log and prints it."""
    ts    = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    pipeline_log.append(entry)
    if len(pipeline_log) > 200:
        pipeline_log.pop(0)
    print(entry)


def run_pipeline(bankroll: float = 1000.0, paper_only: bool = True) -> dict:
    """
    Runs the full pipeline once: scan → predict → risk check → (paper) trade.

    Args:
        bankroll:   Current account balance for position sizing
        paper_only: If True, logs trades but does not execute on exchange

    Returns:
        Summary dict with counts of markets, signals, and trades taken
    """
    global pipeline_running
    pipeline_running = True
    summary = {"markets": 0, "signals": 0, "trades": 0, "blocked": 0}

    try:
        log("Pipeline starting...")

        # ── Step 1: Scan ──────────────────────────────────────────────────────
        markets          = scan_markets()
        summary["markets"] = len(markets)
        log(f"Scan: {len(markets)} tradeable markets found")

        if not markets:
            log("No markets — pipeline stopping")
            return summary

        # ── Step 2: Predict ───────────────────────────────────────────────────
        signals            = run_predictions(markets)
        summary["signals"] = len(signals)
        log(f"Predictions: {len(signals)} signals generated")

        if not signals:
            log("No signals this scan — nothing to trade")
            return summary

        # ── Step 3: Risk check + (paper) trade ───────────────────────────────
        for signal in signals:
            approved, reason = check_all_risks(signal, bankroll)

            if not approved:
                log(f"BLOCKED: {signal['title'][:40]} — {reason}")
                summary["blocked"] += 1
                continue

            position = build_position(signal, bankroll)

            if paper_only:
                save_trade(position)
                log(f"PAPER TRADE: BUY {position['direction']} '{position['market_title'][:38]}' ${position['size']:.2f}")
                summary["trades"] += 1
            else:
                # Real execution would go here
                # from bot.executor import execute_trade
                # execute_trade(position)
                log("Live trading not yet enabled — set paper_only=False in app.py when ready")

        log(f"Pipeline complete — {summary['trades']} trades, {summary['blocked']} blocked")

    except Exception as e:
        log(f"Pipeline ERROR: {e}")
    finally:
        pipeline_running = False

    return summary


def get_log() -> list:
    """Returns the current pipeline log (most recent first)."""
    return list(reversed(pipeline_log[-50:]))


def is_running() -> bool:
    """Returns True if a pipeline scan is currently in progress."""
    return pipeline_running
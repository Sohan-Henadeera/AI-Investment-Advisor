# =============================================================================
# DATA QUALITY:
#   Polymarket: 67% accuracy, highest volume, no auth needed
#   Kalshi:     78% accuracy, most accurate, requires API key
# =============================================================================

from datetime import datetime, timedelta
from config import MIN_VOLUME, MAX_DAYS_TO_EXPIRY
from database import save_ma, save_market
# Import live price feed
try:
    from bot.live_prices import fetch_polymarket_markets, fetch_kalshi_markets, get_live_markets
    LIVE_FEED_AVAILABLE = True
except ImportError:
    LIVE_FEED_AVAILABLE = False


def get_demo_markets() -> list:
    """Fallback demo markets when APIs are unavailable."""
    now = datetime.now()
    return [
        {"id":"DEMO-001","title":"Will the RBA cut rates in May 2026?","platform":"demo","yes_price":0.52,"no_price":0.48,"volume":450,"days_to_expiry":20},
        {"id":"DEMO-002","title":"Will Australia win the next cricket test?","platform":"demo","yes_price":0.61,"no_price":0.39,"volume":820,"days_to_expiry":7},
        {"id":"DEMO-003","title":"Will Bitcoin exceed $100k by end of April?","platform":"demo","yes_price":0.38,"no_price":0.62,"volume":1200,"days_to_expiry":17},
        {"id":"DEMO-004","title":"Will the US Fed hold rates in June 2026?","platform":"demo","yes_price":0.71,"no_price":0.29,"volume":2100,"days_to_expiry":25},
        {"id":"DEMO-005","title":"Will there be a US government shutdown in Q2?","platform":"demo","yes_price":0.29,"no_price":0.71,"volume":670,"days_to_expiry":14},
        {"id":"DEMO-006","title":"Will Nvidia stock hit $200 before June?","platform":"demo","yes_price":0.44,"no_price":0.56,"volume":980,"days_to_expiry":22},
        {"id":"DEMO-007","title":"Will CPI inflation fall below 3% in April?","platform":"demo","yes_price":0.58,"no_price":0.42,"volume":1540,"days_to_expiry":18},
    ]


def parse_days_to_expiry(end_date: str) -> int:
    """Calculates days until a market expires from various date formats."""
    if not end_date:
        return 15
    try:

        dt = datetime.fromisoformat(end_date.replace("Z","").replace("+00:00",""))
        return max(0, (dt - datetime.now()).days)
    except Exception:
        return 15


def flag_market(yes_price: float, volume: float, arb_flag: bool = False) -> bool:
    """
    Returns True if a market is interesting enough to predict on.
    Flags: near 50/50 with volume, OR arbitrage opportunity between platforms.
    """
    if arb_flag:
        return True  # Price discrepancy between Polymarket and Kalshi
    if 0.35 <= yes_price <= 0.65 and volume >= MIN_VOLUME:
        return True
    return False


def normalise_market(raw: dict, platform: str) -> dict | None:
    """
    Converts a raw API market dict into our standard format.
    Returns None if the market doesn't meet basic criteria.
    """
    yes_price  = float(raw.get("yes_price", 0.5))
    volume     = float(raw.get("volume", 0) or 0)
    end_date   = raw.get("end_date") or raw.get("close_time") or raw.get("endDate","")
    days_left  = parse_days_to_expiry(end_date) if end_date else 15

    # Filters
    if volume < MIN_VOLUME:           return None
    if days_left > MAX_DAYS_TO_EXPIRY: return None
    if yes_price <= 0.02 or yes_price >= 0.98: return None

    return {
        "id":            raw.get("id",""),
        "title":         raw.get("title","Unknown"),
        "platform":      platform,
        "yes_price":     round(yes_price, 4),
        "no_price":      round(1 - yes_price, 4),
        "volume":        volume,
        "days_to_expiry":days_left,
        "poly_price":    raw.get("poly_price"),
        "kalshi_price":  raw.get("kalshi_price"),
        "spread":        raw.get("spread"),
        "arb_flag":      raw.get("arb_flag", False),
        "flagged":       0, 
    }


def scan_markets() -> list:
    """
    Main scan function — fetches live data, filters, flags, saves, and returns markets.
    Uses Polymarket as primary (free, no auth), Kalshi supplementary (needs key).
    """
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Scanning markets (live feed)...")

    tradeable = []
    skipped   = 0
    source    = "demo"

    # Try live feed first 
    if LIVE_FEED_AVAILABLE:
        live = get_live_markets(use_cache=False)
        raw_markets = live.get("combined", [])

        if raw_markets:
            source = f"live ({live['poly_count']} Polymarket, {live['kalshi_count']} Kalshi)"
        else:
            raw_markets = get_demo_markets()
            source = "demo (live feed empty)"
    else:
        raw_markets = get_demo_markets()
        source = "demo (live_prices module not available)"

    print(f"  Source: {source}")

    for raw in raw_markets:
        market = normalise_market(raw, raw.get("platform","polymarket"))
        if market is None:
            skipped += 1
            continue

        market["flagged"] = 1 if flag_market(
            market["yes_price"],
            market["volume"],
            market.get("arb_flag", False)
        ) else 0

        save_market(market)
        tradeable.append(market)

    # Sort: arb flags first, then flagged, then by volume
    tradeable.sort(key=lambda x: (
        -x.get("arb_flag", 0),
        -x.get("flagged", 0),
        -x.get("volume", 0)
    ))

    arb_count     = sum(1 for m in tradeable if m.get("arb_flag"))
    flagged_count = sum(1 for m in tradeable if m.get("flagged"))
    print(f"  ✓ {len(tradeable)} tradeable ({skipped} skipped, {flagged_count} flagged, {arb_count} arb opportunities)")
    return tradeable
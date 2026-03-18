# =============================================================================
# bot/live_prices.py — FREE LIVE PRICE FEED (WORKS FROM AUSTRALIA)
# =============================================================================
# Three data sources, all 100% free, no API key, no geo-restrictions:
#
#   POLYMARKET  — world's largest prediction market, read-only is free & open
#   METACULUS   — crowd forecasting, fully public API, no auth needed
#   MANIFOLD    — play-money markets, no restrictions anywhere
#
# WHY THREE: each has different participants and biases. Agreement = strong
# signal. Disagreement = valuable info for the AI advisor.
#
# TO ADD A NEW SOURCE: add fetch_* function and call it in get_live_markets()
# TO CHANGE CACHE TIME: edit CACHE_TTL (seconds)
# =============================================================================

import requests
import time
import json
from datetime import datetime

CACHE_TTL      = 60
POLYMARKET_URL = "https://gamma-api.polymarket.com/markets"
METACULUS_URL  = "https://www.metaculus.com/api2/questions/"
MANIFOLD_URL   = "https://api.manifold.markets/v0/markets"

_cache = {}


def _get_cached(key, fetch_fn, ttl=CACHE_TTL):
    """Returns cached data or refreshes. Prevents hammering APIs."""
    now = time.time()
    if key in _cache and now - _cache[key]["ts"] < ttl:
        return _cache[key]["data"]
    result = fetch_fn()
    _cache[key] = {"data": result, "ts": now}
    return result


# =============================================================================
# POLYMARKET — largest prediction market, read-only free from anywhere
# =============================================================================

def fetch_polymarket(limit=100):
    """
    Fetches active markets from Polymarket Gamma API.
    No auth needed. Public read access works from Australia.
    """
    try:
        resp = requests.get(POLYMARKET_URL, params={
            "active": "true", "closed": "false",
            "limit": limit, "order": "volume", "ascending": "false",
        }, timeout=12)

        if resp.status_code != 200:
            print(f"  ✗ Polymarket {resp.status_code}")
            return []

        markets = []
        for m in resp.json():
            try:
                prices    = json.loads(m.get("outcomePrices", '["0.5","0.5"]'))
                yes_price = round(float(prices[0]), 4)
            except Exception:
                yes_price = 0.5

            if yes_price <= 0.02 or yes_price >= 0.98: continue
            if float(m.get("volume", 0) or 0) < 100:   continue

            markets.append({
                "id":        m.get("conditionId", m.get("id", "")),
                "slug":      m.get("slug", ""),
                "title":     m.get("question", m.get("title", "")),
                "source":    "polymarket",
                "yes_price": yes_price,
                "no_price":  round(1 - yes_price, 4),
                "volume":    float(m.get("volume", 0) or 0),
                "end_date":  m.get("endDate", ""),
                "category":  m.get("category", "General"),
                "url":       f"https://polymarket.com/event/{m.get('slug','')}",
            })

        print(f"  Polymarket: {len(markets)} markets")
        return markets

    except requests.exceptions.ConnectionError:
        print("  ✗ Cannot reach Polymarket")
        return []
    except Exception as e:
        print(f"  ✗ Polymarket error: {e}")
        return []


# =============================================================================
# METACULUS — calibrated crowd forecasting, fully public, great for AU events
# =============================================================================

def fetch_metaculus(limit=50):
    """
    Fetches open binary questions from Metaculus public API.
    No auth. Works from Australia. Highly calibrated crowd forecasts.
    """
    try:
        resp = requests.get(METACULUS_URL, params={
            "status": "open", "forecast_type": "binary",
            "order_by": "-activity", "limit": limit, "format": "json",
        }, timeout=12)

        if resp.status_code != 200:
            print(f"  ✗ Metaculus {resp.status_code}")
            return []

        markets = []
        for q in resp.json().get("results", []):
            cp = q.get("community_prediction", {})
            if isinstance(cp, dict):
                yes_price = cp.get("full", {}).get("q2")
            else:
                yes_price = cp

            if yes_price is None: continue
            yes_price = round(float(yes_price), 4)
            if yes_price <= 0.02 or yes_price >= 0.98: continue

            forecasters = int(q.get("number_of_forecasters", 0) or 0)
            if forecasters < 5: continue

            markets.append({
                "id":          f"metaculus-{q.get('id','')}",
                "slug":        str(q.get("id", "")),
                "title":       q.get("title", ""),
                "source":      "metaculus",
                "yes_price":   yes_price,
                "no_price":    round(1 - yes_price, 4),
                "volume":      float(forecasters) * 10,
                "forecasters": forecasters,
                "end_date":    q.get("close_time", ""),
                "category":    "Forecasting",
                "url":         f"https://metaculus.com{q.get('page_url','')}",
            })

        print(f"  Metaculus: {len(markets)} questions")
        return markets

    except requests.exceptions.ConnectionError:
        print("  ✗ Cannot reach Metaculus")
        return []
    except Exception as e:
        print(f"  ✗ Metaculus error: {e}")
        return []


# =============================================================================
# MANIFOLD MARKETS — play-money, zero geo-restrictions, good AU coverage
# =============================================================================

def fetch_manifold(limit=50):
    """
    Fetches active binary markets from Manifold Markets public API.
    Play-money only — no legal issues anywhere. Good for general topics.
    """
    try:
        resp = requests.get(MANIFOLD_URL, params={
            "sort": "most-popular", "filter": "open",
            "limit": limit, "outcomeType": "BINARY",
        }, timeout=12)

        if resp.status_code != 200:
            print(f"  ✗ Manifold {resp.status_code}")
            return []

        markets = []
        for m in resp.json():
            prob = m.get("probability")
            if prob is None: continue
            yes_price = round(float(prob), 4)
            if yes_price <= 0.02 or yes_price >= 0.98: continue

            traders = int(m.get("uniqueBettorCount", 0) or 0)
            if traders < 5: continue

            categories = m.get("groupLinks", [])
            category   = categories[0].get("name", "General") if categories else "General"

            markets.append({
                "id":       m.get("id", ""),
                "slug":     m.get("slug", ""),
                "title":    m.get("question", ""),
                "source":   "manifold",
                "yes_price":yes_price,
                "no_price": round(1 - yes_price, 4),
                "volume":   float(m.get("volume", 0) or 0),
                "traders":  traders,
                "end_date": "",
                "category": category,
                "url":      f"https://manifold.markets/{m.get('creatorUsername','')}/{m.get('slug','')}",
            })

        print(f"  Manifold: {len(markets)} markets")
        return markets

    except requests.exceptions.ConnectionError:
        print("  ✗ Cannot reach Manifold")
        return []
    except Exception as e:
        print(f"  ✗ Manifold error: {e}")
        return []


# =============================================================================
# COMBINED LIVE FEED
# =============================================================================

def get_live_markets(use_cache=True):
    """
    Fetches from all three platforms and cross-references similar events.
    Returns consensus prices plus flags where platforms disagree (arb signal).

    Return shape:
      {
        polymarket, metaculus, manifold,  — raw lists per platform
        combined,                         — merged, consensus-priced list
        last_updated, poly_count, meta_count, manifold_count
      }
    """
    def fetch():
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Fetching live markets...")
        poly     = fetch_polymarket(100)
        meta     = fetch_metaculus(50)
        manifold = fetch_manifold(50)

        all_markets = poly + meta + manifold
        combined    = []
        matched_ids = set()

        for m in all_markets:
            if m["id"] in matched_ids:
                continue

            # Find the same event on other platforms
            similar = []
            for other in all_markets:
                if other["id"] == m["id"]:          continue
                if other["source"] == m["source"]:  continue
                if _similarity(m["title"], other["title"]) > 0.35:
                    similar.append(other)
                    matched_ids.add(other["id"])

            # Build per-source prices dict
            prices = {m["source"]: m["yes_price"]}
            for s in similar:
                prices[s["source"]] = s["yes_price"]

            all_p      = list(prices.values())
            avg_price  = round(sum(all_p) / len(all_p), 4)
            spread     = round(max(all_p) - min(all_p), 4) if len(all_p) > 1 else 0
            disagree   = spread > 0.05 and len(all_p) > 1

            combined.append({
                **m,
                "yes_price":       avg_price,
                "poly_price":      prices.get("polymarket"),
                "meta_price":      prices.get("metaculus"),
                "manifold_price":  prices.get("manifold"),
                "platform_spread": spread,
                "platforms":       list(prices.keys()),
                "platform_count":  len(prices),
                "disagree_flag":   disagree,
                "arb_flag":        disagree,
            })
            matched_ids.add(m["id"])

        # Sort: multi-platform first (more confident), then by volume
        combined.sort(key=lambda x: (-x["platform_count"], -x.get("volume", 0)))

        print(f"  ✓ Combined: {len(combined)} markets")
        return {
            "polymarket":     poly,
            "metaculus":      meta,
            "manifold":       manifold,
            "combined":       combined,
            "last_updated":   datetime.now().strftime("%H:%M:%S"),
            "poly_count":     len(poly),
            "meta_count":     len(meta),
            "manifold_count": len(manifold),
        }

    return _get_cached("live_markets", fetch) if use_cache else fetch()


def get_market_price(title: str) -> dict:
    """Looks up live price for a market by approximate title match."""
    markets  = get_live_markets()
    best     = None
    best_s   = 0

    for m in markets.get("combined", []):
        s = _similarity(title.lower(), m["title"].lower())
        if s > best_s:
            best_s = s
            best   = m

    if best and best_s > 0.3:
        return {
            "found":           True,
            "title":           best["title"],
            "yes_price":       best["yes_price"],
            "poly_price":      best.get("poly_price"),
            "meta_price":      best.get("meta_price"),
            "manifold_price":  best.get("manifold_price"),
            "platform_spread": best.get("platform_spread"),
            "disagree_flag":   best.get("disagree_flag", False),
            "platforms":       best.get("platforms", []),
            "platform_count":  best.get("platform_count", 1),
            "volume":          best.get("volume", 0),
            "match_score":     round(best_s, 2),
            "url":             best.get("url", ""),
        }
    return {"found": False}


def refresh_watchlist_prices(watchlist: list) -> dict:
    """
    Auto-refreshes prices for all watchlist items from live data.
    Returns {item_id: price_data} for matched items.
    """
    updates = {}
    markets = get_live_markets()

    for item in watchlist:
        if not item.get("title"): continue
        best   = None
        best_s = 0

        for m in markets.get("combined", []):
            s = _similarity(item["title"].lower(), m["title"].lower())
            if s > best_s:
                best_s = s
                best   = m

        if best and best_s > 0.35:
            updates[item["id"]] = {
                "new_price":       best["yes_price"],
                "poly_price":      best.get("poly_price"),
                "meta_price":      best.get("meta_price"),
                "manifold_price":  best.get("manifold_price"),
                "platform_spread": best.get("platform_spread"),
                "disagree_flag":   best.get("disagree_flag", False),
                "platforms":       best.get("platforms", []),
                "match_score":     round(best_s, 2),
                "matched_title":   best["title"],
            }

    return updates


def _similarity(a: str, b: str) -> float:
    """Word-overlap similarity. Returns 0.0 to 1.0."""
    noise = {"will","the","a","an","in","of","to","by","be","is","are",
             "for","on","at","and","or","not","it","this","that"}
    wa = set(a.lower().split()) - noise
    wb = set(b.lower().split()) - noise
    if not wa or not wb: return 0.0
    return len(wa & wb) / len(wa | wb)


# =============================================================================
# QUICK TEST — python bot/live_prices.py
# =============================================================================

if __name__ == "__main__":
    print("Testing all three AU-accessible prediction market APIs...\n")

    print("1. Polymarket (read-only, no auth):")
    for m in fetch_polymarket(5)[:3]:
        print(f"   {m['title'][:55]:<55} {m['yes_price']:.0%}")

    print("\n2. Metaculus (public, no auth):")
    for m in fetch_metaculus(5)[:3]:
        print(f"   {m['title'][:55]:<55} {m['yes_price']:.0%}  ({m.get('forecasters',0)} forecasters)")

    print("\n3. Manifold (play-money, no restrictions):")
    for m in fetch_manifold(5)[:3]:
        print(f"   {m['title'][:55]:<55} {m['yes_price']:.0%}  ({m.get('traders',0)} traders)")

    print("\n4. Combined:")
    data = get_live_markets(use_cache=False)
    print(f"   {len(data['combined'])} total | {data['poly_count']} Poly + {data['meta_count']} Meta + {data['manifold_count']} Manifold")
    disagree = sum(1 for m in data["combined"] if m["disagree_flag"])
    print(f"   Platform disagreements: {disagree}")
# =============================================================================
# config.py — SINGLE SOURCE OF TRUTH FOR ALL SETTINGS
# =============================================================================
# Edit this file to change any bot behaviour.
# Every setting is documented with what it does and safe values to try.
# =============================================================================

# ── KALSHI DEMO API ──────────────────────────────────────────────────────────
# Sign up free at https://demo.kalshi.com → Account → API
# Leave as-is to use built-in demo data (no real money, no account needed)
KALSHI_API_KEY    = "YOUR_KALSHI_DEMO_KEY_HERE"
KALSHI_API_SECRET = "YOUR_KALSHI_DEMO_SECRET_HERE"
KALSHI_BASE_URL   = "https://demo-api.kalshi.co/trade-api/v2"

# ── LOCAL AI (OLLAMA) ────────────────────────────────────────────────────────
# Install Ollama from https://ollama.com then run: ollama pull llama3
# All AI runs on your machine — zero API cost, zero data leaves your device
OLLAMA_MODEL = "llama3"
OLLAMA_URL   = "http://localhost:11434/api/generate"

# ── RISK MANAGEMENT ──────────────────────────────────────────────────────────
# MIN_EDGE: only trade when our AI estimate beats market by this much (4% = 0.04)
# Safe range: 0.03 to 0.08. Lower = more trades, higher = fewer but stronger
MIN_EDGE = 0.04

# KELLY_FRACTION: what fraction of full Kelly to bet. 0.25 = quarter Kelly (safe)
# Safe range: 0.1 (very conservative) to 0.5 (aggressive). Never use 1.0
KELLY_FRACTION = 0.25

# MAX_POSITION_PCT: max % of bankroll on any single trade (5% = 0.05)
MAX_POSITION_PCT = 0.05

# MAX_DAILY_LOSS: stop trading for the day if losses exceed this % (15% = 0.15)
MAX_DAILY_LOSS = 0.15

# MAX_POSITIONS: maximum number of open trades at once
MAX_POSITIONS = 15

# ── SCANNER SETTINGS ─────────────────────────────────────────────────────────
# MIN_VOLUME: ignore markets with fewer contracts than this
MIN_VOLUME = 200

# MAX_DAYS_TO_EXPIRY: only trade markets resolving within this many days
MAX_DAYS_TO_EXPIRY = 30

# SCAN_INTERVAL_MIN: how often the auto-scan runs (minutes)
SCAN_INTERVAL_MIN = 15

# ── DATABASE ─────────────────────────────────────────────────────────────────
# SQLite file stored locally — no cloud, no setup required
DB_PATH = "predbot.db"

# ── WEB SERVER ───────────────────────────────────────────────────────────────
PORT = 5000
HOST = "0.0.0.0"  # 0.0.0.0 = accessible on your local network, 127.0.0.1 = this machine only
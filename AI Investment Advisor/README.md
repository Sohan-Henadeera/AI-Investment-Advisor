# AI Investment Advisor

AI-powered prediction market trading bot with live market data, 
CommSec-style, and a local AI advisor.

## Features
- Live market prices from Polymarket (free) + Kalshi
- CommSec-style watchlist — track holdings with P&L
- Local AI advisor via Ollama — daily reports + chat
- Automated scan → predict → risk pipeline
- Paper trading mode (no real money)
- Password-protected web GUI

## Stack
- Python + Flask (backend)
- Ollama + Llama 3 (local AI, zero cost)
- SQLite (local database)
- Vanilla HTML/CSS/JS (frontend)

## Setup

### 1. Install dependencies
pip install flask requests

### 2. Install Ollama
Download from https://ollama.com then run:
ollama pull llama3

### 3. Configure
Edit config.py — add your Kalshi demo API key (optional, 
Polymarket works without any key)

### 4. Run
python app.py

Open http://localhost:5000

## Project structure
Main_v1b/
├── app.py          — entry point
├── config.py       — all settings
├── database.py     — SQLite logic
├── gui.html        — web frontend
├── bot/
│   ├── scanner.py      — market discovery
│   ├── predictor.py    — AI probability
│   ├── risk.py         — Kelly sizing
│   ├── pipeline.py     — orchestration
│   ├── advisor.py      — AI reports + chat
│   └── live_prices.py  — live feed
└── api/
    ├── auth.py         — login + sessions
    └── routes.py       — all endpoints

## Disclaimer
Paper trading only. Not financial advice.
```


```
Initial commit — AI Investment Advisor v1 with live Polymarket feed and AI watchlist advisor
```
```
main          ← stable, working version always lives here
dev           ← where you build new features
feature/xxx   ← one branch per new feature, merged into dev
```

**Topics to add to the repo** (makes it discoverable on GitHub):
```
prediction-markets polymarket kalshi python flask ollama ai-trading local-ai paper-trading fintech

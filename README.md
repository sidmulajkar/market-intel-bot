# market-intel-bot

AI-powered market intelligence bot that sends daily Telegram messages (text + heatmaps) on Indian markets. Regime-detecting decision engine with internal arbitration and self-awareness.

## Features
- **Market State Dashboard** — Phase classification (EXPANSION/RECOVERY/NEUTRAL/DISTRIBUTION/CONTRACTION) with stance, exposure range, and risk watch
- **8-Signal Weighted Composite** — Bull/Bear, FII footprint, cross-asset regime, breadth, fear/greed, credit stress, sector regime, volatility — scored -1 to +1, missing signals excluded
- **Cross-Asset Regime** — 12+ detectors synthesized into single label (RISK_ON/RISK_OFF/STAGFLATION/etc.) with confirmation %
- **Institutional Signals** — Sector regime, volatility compression, risk appetite, breadth thrust, FII footprint (all from stored data)
- **Earnings Season Regime** — PEAK_WEEK/ACTIVE/APPROACHING/QUIET classification
- **Signal Arbitration** — Master signal synthesis with contradiction scoring and dynamic weights
- **Global indices heatmap** — 18 indices with world map visualization
- **India sector heatmap** — Nifty sector performance
- **FII/DII flow tracking** — Cash market + F&O participant positioning
- **Options chain analysis** — PCR, Max Pain, OI zones, GEX, 25D skew
- **MF flow intelligence** — AMFI category flows, SIP trends
- **AI-generated market briefs** — Groq/Google AI with FinBERT sentiment
- **Top Movers** — Dynamic Nifty 50 + US majors (not static watchlist)

## Jobs
- `market_intel.py` — Full 11-block AI analysis with Market State Dashboard (7 AM / 6 PM)
- `morning_brief.py` — Heatmaps + short brief + Market State Dashboard (8 AM)
- `evening_report.py` — US session heatmap + Market State Dashboard (8 PM)
- `midday_scan.py` — Market regime scanner (12:30 PM)
- `market_open.py` — Opening briefing with dynamic top movers (9:15 AM)
- `market_close.py` — EOD summary with dynamic top movers (3:30 PM)
- `weekly_digest.py` — Prediction scorecard, FII pattern, regime shift, institutional signals
- `fii_dii_fetch.py` — Daily FII/DII data (5 AM)
- `mf_intelligence.py` — Monthly AMFI flows

## Tech Stack
Python, Supabase, Telegram Bot, Groq/Google AI, yfinance, NSE/AMFI/SEBI data, FinBERT sentiment

## Running
```bash
python jobs/market_intel.py morning
python jobs/market_intel.py evening
```

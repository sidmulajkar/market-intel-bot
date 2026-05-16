# market-intel-bot

AI-powered market intelligence bot that sends daily Telegram messages (text + heatmaps) on Indian markets.

## Features
- Global indices heatmap
- India sector heatmap  
- FII/DII flow tracking
- Options chain analysis (PCR, Max Pain, OI zones)
- MF flow intelligence
- AI-generated market briefs

## Jobs
- `market_intel.py` — Full AI analysis (morning/evening modes)
- `morning_brief.py` — Heatmaps + short brief
- `evening_report.py` — US session + EOD summary
- `fii_dii_fetch.py` — Daily FII/DII data
- `mf_intelligence.py` — Monthly MF flows

## Tech Stack
Python, Supabase, Telegram Bot, Groq/Google AI, NSE/AMFI data sources

## Running
```bash
python jobs/market_intel.py morning
python jobs/market_intel.py evening
```

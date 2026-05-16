# 📘 VERIFIED SPECIFICATION — Market Intel Bot

**Status**: ✅ **PHASE 1 COMPLETE + PHASE 2 ENHANCEMENTS BUILT**
**Last Updated**: 2026-05-16

---

## 1. ARCHITECTURE

| Path | Flow | Mechanism | Status |
| :--- | :--- | :--- | :--- |
| **Path A (Visual)** | `fetch` → `heatmap_generator` → `send_image` | **Telegram Image** (No AI) | ✅ Working |
| **Path B (AI)** | `fetch` → `formatters.py` → `master_prompt.txt` → `ai_engine.py` → `send_text` | **Telegram Text** (AI Analysis) | ✅ Working |

---

## 2. DATA SOURCES (ALL IMPLEMENTED)

| Data | Source | Fetcher Function | Status |
| :--- | :--- | :--- | :--- |
| **Global Indices (18)** | yfinance | `fetch_global_indices()` | ✅ |
| **Watchlist Stocks** | yfinance | `fetch_watchlist_data()` | ✅ |
| **Global News** | Finnhub | `fetch_general_news()` | ✅ |
| **Indian News** | RSS (ET, MoneyControl, Livemint) | `fetch_indian_news()` | ✅ |
| **Sentiment** | HuggingFace | `ai.sentiment()` (FinBERT) | ✅ |
| **USDINR, Brent, Gold, VIX, DXY** | yfinance | `fetch_macro_anchors()` | ✅ |
| **FII/DII Flows** | NSE India | `jobs/fii_dii_fetch.py` → Supabase | ✅ |
| **MF Category Flows** | AMFI | `jobs/mf_intelligence.py` → Supabase | ✅ |
| **Sector FPI** | NSE/SEBI | `src/fii_sector.py` | ✅ |
| **F&O Participant OI** | NSE | `src/fii_derivatives.py` | ✅ |
| **Options Chain** | NSE | `src/options_engine.py` | ✅ |
| **Market Breadth** | NSE | `fetch_market_breadth()` | ✅ |
| **Insider Activity** | NSE bulk/block deals | `src/insider_tracker.py` | ✅ |
| **Shareholding** | yfinance | `src/shareholding_tracker.py` | ✅ |

---

## 3. INTELLIGENCE LAYERS (ALL IMPLEMENTED)

### 3A. `src/formatters.py` — Block Formatters
| Function | Block | Status |
| :--- | :--- | :--- |
| `format_context_block()` | Block 0: Market Posture | ✅ |
| `format_global_indices()` | Block 1: Global Indices | ✅ |
| `format_macro_anchors()` | Block 2: Macro Anchors | ✅ |
| `format_sector_fpi()` (via `fii_sector.py`) | Block 3: Sector FPI | ✅ |
| `format_flows()` | Block 4: FII/DII Flows | ✅ |
| `format_options_block()` | Block 5: Derivatives | ✅ |
| `format_news()` | Block 6: News Intelligence | ✅ |
| `format_insider_activity()` | Block 7: Insider Activity | ✅ |
| `format_watchlist()` | Block 8: Watchlist + TA | ✅ |
| *(Not implemented)* | Block 9: Macro Calendar | ❌ Empty |
| `format_mf_flows()` | Block 10: MF Flows | ✅ |

### 3B. Intelligence Modules
| Module | Purpose | Status |
| :--- | :--- | :--- |
| `src/context_engine.py` | Bull/Bear scoring, z-scores, streaks, DII absorption, narratives | ✅ |
| `src/quant_enrichment.py` | Percentiles, cross-signal correlations, regime detection, news impact scoring | ✅ |
| `src/technical_analysis.py` | RSI, 20/50/200-DMA, S/R, MACD, Bollinger Bands | ✅ |
| `src/options_engine.py` | Max Pain, PCR, OI zones, OI shift detection | ✅ |
| `src/fii_derivatives.py` | F&O participant OI, FII L/S ratio, hedging detection | ✅ |
| `src/fii_sector.py` | FPI sector-wise flows, rotation signals | ✅ |
| `src/insider_tracker.py` | NSE bulk/block deals, Indian stock filtering | ✅ |
| `src/shareholding_tracker.py` | Promoter/FII/DII/Public % with QoQ comparison | ✅ |

---

## 4. AI ENGINE

**File**: `src/ai_engine.py`

**Routing**:
- `ai.analyze(task="fast", prompt)` → Groq (llama-3.3-70b) → Google (gemini-2.0-flash)
- `ai.analyze(task="volume", prompt)` → Google (gemini-2.0-flash) → Groq
- `ai.sentiment(text)` → FinBERT via HuggingFace API
- System prompt prepended to user prompt (workaround for older SDK)

**Environment Variables**:
| Variable | Where Used | Note |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | ai_engine.py | |
| `GOOGLE_AI_KEY` | ai_engine.py | ⚠️ NOT `GOOGLE_API_KEY` |
| `HF_KEY` | ai_engine.py | For FinBERT sentiment |
| `FINNHUB_KEY` | data_fetcher.py | ⚠️ NOT `FINNHUB_API_KEY` |
| `SUPABASE_URL`, `SUPABASE_KEY` | db.py | |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | telegram_sender.py | |

---

## 5. SUPABASE TABLES

| Table | Retention | Purge Logic |
| :--- | :--- | :--- |
| `fii_dii_flows` | 61 Trading Days | Trading-day-aware purge |
| `mf_flows` | 2 Months | Delete rows older than 60 days |
| `market_snapshots` | 90 Days | Standard date cutoff |
| `options_snapshots` | 7 Days | Morning/evening snapshots |
| `shareholding_snapshots` | Quarterly | QoQ comparison |
| `sent_alerts` | 30 Days | Deduplication |
| `analysis_cache` | TTL | Expires_at based |

---

## 6. JOBS & WORKFLOWS

All triggered by **cron-job.org** → GitHub `workflow_dispatch`. Mon-Fri only.

| Job File | Schedule (IST) | Purpose | Status |
| :--- | :--- | :--- | :--- |
| `fii_dii_fetch.py` | 5:00 AM | NSE FII/DII → Supabase | ✅ |
| `morning_brief.py` | 6:30 AM | Heatmaps + short AI brief | ✅ |
| `market_intel.py` (morning) | 7:00 AM | Blocks 0,1,2,4,5,6,8 | ✅ |
| `market_intel.py` (evening) | 6:00 PM | All blocks + shareholding QoQ | ✅ |
| `evening_report.py` | 6:15 PM | US heatmap + AI brief | ✅ |
| `mf_intelligence.py` | 8th monthly | AMFI category flows → Supabase | ✅ |
| `market_close.py` | 3:30 PM | EOD summary | ✅ |
| `insider_tracker.py` | 4:00 PM | Bulk/block deals | ✅ |

---

## 7. KNOWN LIMITATIONS

1. **Block 9 (Macro Calendar)** — Not implemented, always empty
2. **Cross-signal win rates** — Hardcoded estimates, not backtested
3. **Options engine** — Max Pain is proxy (highest total OI strike), OI shift thresholds now dynamic
4. **Gemini free tier** — Daily quota exhausted easily; Groq fallback works
5. **NSE API fragility** — Session cookies required, rate limiting causes silent failures
6. **Weekend data gaps** — NSE APIs return nothing on weekends (expected)

---

## 8. NEXT PHASES (PLANNED)

See improvement plan at `/home/sid/.openclaude/plans/flickering-knitting-sparkle.md`

**Priority order:**
1. Quant enrichment hardening (backtest cross-signals, breadth percentile)
2. Valuation intelligence (P/E, P/B, earnings yield, market-cap-to-GDP)
3. Derivatives enhancement (VIX term structure, VIX-RV spread, rollover)
4. Macro intelligence (Block 9 calendar, real rates, yield curve)
5. Contrarian layer (SIP concentration, IPO frenzy, sentiment extremes)
6. Performance (caching, parallel fetches, unified NSE session)

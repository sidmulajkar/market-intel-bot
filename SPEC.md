# 📘 VERIFIED SPECIFICATION — Market Intel Bot (Phase 1)

**Status**: ✅ **VERIFIED AGAINST REPO** | **DO NOT DEVIATE**
**Last Updated**: 2026-05-14

---

## 1. ARCHITECTURE (THE GOLDEN RULE)

| Path | Flow | Mechanism | Status |
| :--- | :--- | :--- | :--- |
| **Path A (Visual)** | `fetch` → `heatmap_generator` → `send_image` | **Telegram Image** (No AI) | ✅ Exists |
| **Path B (AI)** | `fetch` → `formatters.py` → `master_prompt.txt` → `ai_engine.py` → `send_text` | **Telegram Text** (AI Analysis) | 🚧 **TO BE BUILT** |

> **⚠️ CRITICAL**: Existing jobs (`morning_brief`, `evening_report`) build prompts **inline**. Phase 1 introduces `src/formatters.py` and `config/master_prompt.txt` to standardize Path B.

---

## 2. DATA SOURCES (VERIFIED)

| Data | Source | Fetcher Function | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Global Indices (18)** | yfinance | `fetch_global_indices()` | ✅ Exists | |
| **Watchlist Stocks** | yfinance | `fetch_watchlist_data()` | ✅ Exists | |
| **News** | Finnhub | `fetch_general_news()` | ✅ Exists | |
| **Sentiment** | HuggingFace | `ai.sentiment()` (FinBERT) | ✅ Exists | Uses `HF_KEY` (API, not local) |
| **USDINR, Brent, Gold** | yfinance | **NEW FUNCTION NEEDED** | ❌ Missing | Add to `data_fetcher.py` |
| **FII/DII Flows** | NSE India | **NEW SCRAPER NEEDED** | ❌ Missing | Not in repo. Needs `jobs/fii_dii_fetch.py` |
| **MF Category Flows** | AMFI | **NEW SCRAPER NEEDED** | ❌ Missing | Different from existing `mf_flows.py` (NAV) |
| **Sector Data** | NSE/YFin | TBD | ❌ Missing | Phase 2 |

---

## 3. THE NEW "BRAIN" (PATH B REFACTOR)

### A. `src/formatters.py` (NEW FILE)
**Rule**: 1 Function = 1 Input Block. If fetch fails → return `""` (empty string).

| Function Name | Input Data | Maps To Block |
| :--- | :--- | :--- |
| `format_global_indices()` | 18 indices | **Block 1** |
| `format_macro_anchors()` | USDINR, Brent, Gold | **Block 2** |
| `format_flows()` | FII/DII weekly net | **Block 4** |
| `format_news()` | Validated news + sentiment | **Block 6** |
| `format_watchlist()` | Watchlist close prices | **Block 8** |
| `format_mf_flows()` | AMFI category flows | **Block 10** |
| *(Phase 2)* `format_sectors()` | Sector performance | **Block 3** |
| *(Phase 2)* `format_derivatives()` | PCR + Max Pain | **Block 5** |

### B. `config/master_prompt.txt` (NEW FILE)
- **Static file.** Never changes at runtime.
- **Structure**:
  ```text
  [CONTEXT]
  You are a market analyst. Analyze the following blocks.
  - Cite numbers explicitly (e.g., "Nifty up 1.2%").
  - Distinguish "temporary fear" vs "structural breakdown".
  - If a block is missing, SKIP IT. Do not hallucinate.

  [BLOCK 1: GLOBAL INDICES]
  {block_1_data}

  [BLOCK 2: MACRO ANCHORS]
  {block_2_data}
  ...
  ```

---

## 4. AI ENGINE (VERIFIED - NO CHANGES)

**File**: `src/ai_engine.py`

**Routing**:
- `ai.analyze(task="fast", prompt)` → Groq (llama-3.3-70b) → Google (gemini-1.5-flash)
- `ai.analyze(task="volume", prompt)` → Google (gemini-1.5-flash) → Groq

**Environment Variables (VERIFIED)**:
| Variable | Where Used | Note |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | ai_engine.py | |
| `GOOGLE_AI_KEY` | ai_engine.py | ⚠️ NOT `GOOGLE_API_KEY` |
| `HF_KEY` | ai_engine.py | For FinBERT sentiment |
| `FINNHUB_KEY` | data_fetcher.py | ⚠️ NOT `FINNHUB_API_KEY` |
| `SUPABASE_URL`, `SUPABASE_KEY` | db.py | |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | telegram_sender.py | |

---

## 5. SUPABASE TABLES (SCHEMA UPDATE)

**File**: `src/db.py` (Add these methods + schema)

| Table | Retention | Purge Logic |
| :--- | :--- | :--- |
| `fii_dii_flows` | 61 Trading Days | **Trading Day Aware**: Only purge if 61st trading day exists in DB. |
| `mf_flows` | 2 Months | Delete rows older than 60 days. |
| `market_snapshots` | 90 Days | Existing logic. |
| `analysis_cache` | TTL | Existing logic. |

> **⚠️ ACTION ITEM**: Update `purge_old_data()` in `db.py` to handle `fii_dii_flows` and `mf_flows` specifically.

---

## 6. JOBS & WORKFLOWS (PHASE 1 BUILD LIST)

All triggered by **cron-job.org** → GitHub `workflow_dispatch`.

| Job File | Schedule (IST) | Triggers | Purpose |
| :--- | :--- | :--- | :--- |
| **`fii_dii_fetch.py`** | **5:00 AM** | `fii_dii_fetch.yml` | Scrapes NSE, saves to `fii_dii_flows` table. |
| **`morning_brief.py`** | 6:30 AM | `morning_brief.yml` | **Exists.** Sends heatmaps + short alert. |
| **`market_intel.py`** | **7:00 AM (Morning)** | `market_intel_morning.yml` | **NEW.** Runs "Volume" task. Blocks 1,2,4,6,8. |
| **`market_intel.py`** | **6:00 PM (Evening)** | `market_intel_evening.yml` | **NEW.** Runs "Volume" task. All 10 Blocks. |
| **`evening_report.py`** | 6:15 PM | `evening_report.yml` | **Exists.** Sends US Heatmap + "Fast" AI brief. |
| **`mf_intelligence.py`**| **8th of Month** | `mf_intelligence.yml` | **NEW.** Scrapes AMFI, saves to `mf_flows` table. |

---

## 7. NEW FILES TO CREATE (CHECKLIST)

| Path | Filename | Status |
| :--- | :--- | :--- |
| `src/` | `formatters.py` | TO BUILD |
| `src/` | `commodity_heatmap.py` | TO BUILD |
| `config/` | `master_prompt.txt` | TO BUILD |
| `jobs/` | `fii_dii_fetch.py` | TO BUILD |
| `jobs/` | `market_intel.py` | TO BUILD |
| `jobs/` | `mf_intelligence.py` | TO BUILD |
| `.github/workflows/` | `fii_dii_fetch.yml` | TO BUILD |
| `.github/workflows/` | `market_intel_morning.yml` | TO BUILD |
| `.github/workflows/` | `market_intel_evening.yml` | TO BUILD |
| `.github/workflows/` | `mf_intelligence.yml` | TO BUILD |

---

## 8. ERROR HANDLING RULES (ENFORCED)

1. **Formatter Failure:** If `fetch_global_indices()` crashes, `format_global_indices()` returns `""`.
2. **Prompt Assembly:** `market_intel.py` concatenates blocks. If `block_1 == ""`, the header `[BLOCK 1]` is also skipped.
3. **Total Failure:** If **all 10 blocks** return `""`, the job sends: *"🚨 Market Intel Unavailable: All data sources failed."*

---

## 9. BUILD ORDER (RECOMMENDED)

1. `src/data_fetcher.py` additions — add `fetch_macro_anchors()` for USDINR/Brent/Gold
2. `config/master_prompt.txt` — create the static prompt file
3. `src/formatters.py` — write the 6 core formatters (Blocks 1,2,4,6,8,10)
4. `src/db.py` — add `fii_dii_flows`, `mf_flows` tables + updated purge logic
5. `jobs/fii_dii_fetch.py` + workflow — FII/DII scraping
6. `jobs/mf_intelligence.py` + workflow — MF category flows
7. `src/commodity_heatmap.py` — commodity heatmap
8. `jobs/market_intel.py` — the main AI orchestrator
9. `market_intel_morning.yml` + `market_intel_evening.yml` — workflows

---

## 10. PHASE 2 (DEFERRED)

- BLOCK 3 (Sector Performance)
- BLOCK 5 (Derivatives PCR + Max Pain)
- BLOCK 7 (Insider Activity)
- BLOCK 9 (Macro Calendar)
- `config/nse_holidays_2025-2026.csv` + `is_trading_day()` utility

---

**🚀 READY TO BUILD**
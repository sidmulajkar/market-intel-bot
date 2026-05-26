"""
AI Engine — Groq + Google AI Studio
Fixed: RateLimitError import + correct model names
"""
import os
import re
import json
import time
import requests

# ── GROQ ──────────────────────────────────────────────────────────
try:
    from groq import Groq
    # BUG FIX: RateLimitError is groq.APIStatusError in newer versions
    # Use base Exception and check status code instead
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️  groq not installed")

# ── GOOGLE ────────────────────────────────────────────────────────
try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    print("⚠️  google-generativeai not installed")

# ── GOOGLE SEARCH GROUNDING (via google-genai) ─────────────────────
# Uses Gemini with Google Search Retrieval — Gemini can search the web
# during generation to verify numbers, find fresh news, fill API gaps.
GOOGLE_SEARCH_AVAILABLE = False
try:
    from google import genai as genai_client
    from google.genai import types as genai_types
    GOOGLE_SEARCH_AVAILABLE = True
except ImportError:
    pass  # google-genai not installed — search grounding unavailable

GROQ_KEY   = os.environ.get('GROQ_API_KEY',  '')
GOOGLE_KEY = os.environ.get('GOOGLE_AI_KEY', '')
HF_KEY     = os.environ.get('HF_KEY',        '')

SYSTEM_PROMPT = (
    "You are a quantitative market analyst. Your output must:\n"
    "- Lead with the single most important number and its historical context\n"
    "- Cite specific numbers with 'since [date]' or 'Xth percentile' context\n"
    "- Describe scenarios with conditional language (If X → Y), never assign percentages\n"
    "- Reference cross-signal correlations when active in the data\n"
    "- Never state a number without context (e.g., NOT 'VIX is 18' but 'VIX at 18, 65th percentile of 90D')\n"
    "- Use emojis for visual structure: 📊 📈 🔑 ⚠️ 🟢 🔴\n"
    "- No disclaimers, no padding, no fluff"
)

class AIEngine:

    def __init__(self):
        self.groq_client  = None
        self.google_model = None
        self.google_search_client = None  # google-genai with Search Retrieval

        if GROQ_AVAILABLE and GROQ_KEY:
            try:
                self.groq_client = Groq(api_key=GROQ_KEY)
            except Exception as e:
                print(f"⚠️  Groq init failed: {e}")

        if GOOGLE_AVAILABLE and GOOGLE_KEY:
            try:
                genai.configure(api_key=GOOGLE_KEY)
                # Updated: gemini-1.5-flash deprecated, using gemini-2.0-flash
                self.google_model = genai.GenerativeModel('gemini-2.0-flash')
            except Exception as e:
                print(f"⚠️  Google AI init failed: {e}")

        # Google Search Grounding — uses google-genai SDK
        if GOOGLE_SEARCH_AVAILABLE and GOOGLE_KEY:
            try:
                self.google_search_client = genai_client.Client(api_key=GOOGLE_KEY)
            except Exception as e:
                print(f"⚠️  Google Search client init failed: {e}")

    def analyze(self, task: str, prompt: str) -> str:
        if task == "fast":
            return (self._try_groq(prompt)
                    or self._try_google(prompt)
                    or self._try_google_search(prompt)
                    or "⚠️ AI analysis temporarily unavailable.")
        elif task == "volume":
            return (self._try_google(prompt)
                    or self._try_groq(prompt)
                    or self._try_google_search(prompt)
                    or "⚠️ AI analysis temporarily unavailable.")
        else:
            return (self._try_groq(prompt)
                    or self._try_google(prompt)
                    or self._try_google_search(prompt)
                    or "⚠️ AI analysis temporarily unavailable.")

    @staticmethod
    def _check_output_quality(content: str, min_words: int = 30) -> str:
        """Reject ultra-short outputs that indicate model failure or quota exceeded."""
        if not content:
            return ""
        # Strip common failure phrases
        stripped = content.strip()
        if len(stripped.split()) < min_words:
            print(f"⚠️  AI output too short ({len(stripped.split())} words, need {min_words}): {stripped[:80]}")
            return ""
        return stripped

    @staticmethod
    def _validate_forecast_schema(content: str) -> bool:
        """Check that volume-task AI output contains a structured Forecast.

        Extracts JSON from the response and validates required keys exist
        with valid values. This is the real guard against garbage output —
        word count is only the fast path.
        """
        if not content:
            return False
        # Try to find JSON block in the response
        json_match = re.search(r'\{[^{}]*"direction"[^{}]*\}', content, re.DOTALL)
        if not json_match:
            # Also check for non-JSON structured output with labeled fields
            has_direction = bool(re.search(r'direction\s*[:=]\s*(bullish|bearish|neutral)', content, re.IGNORECASE))
            has_confidence = bool(re.search(r'confidence\s*[:=]\s*(\d+|high|medium|low)', content, re.IGNORECASE))
            if has_direction and has_confidence:
                return True
            print(f"⚠️  AI output lacks structured forecast: no direction/confidence found")
            return False
        try:
            forecast = json.loads(json_match.group())
            direction = forecast.get("direction", "").upper()
            if direction not in ("BULLISH", "BEARISH", "NEUTRAL"):
                print(f"⚠️  AI forecast: invalid direction={forecast.get('direction')}")
                return False
            prob = forecast.get("probability_up")
            if prob is not None and not (0.0 <= prob <= 1.0):
                print(f"⚠️  AI forecast: probability_up={prob} out of [0,1]")
                return False
            return True
        except json.JSONDecodeError:
            print(f"⚠️  AI output: found JSON-like block but parse failed")
            return False

    def _try_groq(self, prompt: str) -> str:
        if not self.groq_client:
            return ""
        for attempt in range(3):
            try:
                resp = self.groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": prompt},
                    ],
                    max_tokens=1000,
                    temperature=0.3,
                )
                raw = resp.choices[0].message.content
                return self._check_output_quality(raw)

            except Exception as e:
                err_str = str(e).lower()
                # BUG FIX: Check for rate limit by string, not exception type
                if "rate_limit" in err_str or "429" in err_str:
                    wait = 30 * (2 ** attempt)
                    print(f"⏳ Groq rate limited — waiting {wait}s")
                    if attempt < 2:
                        time.sleep(wait)
                    else:
                        return ""
                else:
                    print(f"⚠️  Groq error attempt {attempt+1}: {e}")
                    if attempt < 2:
                        time.sleep(5)
                    else:
                        return ""
        return ""

    def _try_google(self, prompt: str) -> str:
        if not self.google_model:
            return ""
        for attempt in range(3):
            try:
                # Prepend system prompt to user prompt (older google-generativeai doesn't support system_instruction)
                full_prompt = f"[SYSTEM INSTRUCTIONS]\n{SYSTEM_PROMPT}\n\n[USER REQUEST]\n{prompt}"
                cfg  = genai.GenerationConfig(
                    max_output_tokens=1000,
                    temperature=0.3,
                )
                resp = self.google_model.generate_content(
                    full_prompt,
                    generation_config=cfg
                )
                return self._check_output_quality(resp.text)
            except Exception as e:
                print(f"⚠️  Google AI error attempt {attempt+1}: {e}")
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
                else:
                    return ""
        return ""

    def _try_google_search(self, prompt: str) -> str:
        """Gemini with Google Search Grounding — searches the web during generation.

        This is the final fallback: when both Groq and standard Gemini fail,
        we use Gemini + Google Search to get live web-grounded analysis.
        The model can verify our numbers against live sources and find
        fresh news that our APIs missed.
        """
        if not self.google_search_client:
            return ""
        try:
            print("   🔍 Falling back to Gemini + Google Search grounding...")
            response = self.google_search_client.models.generate_content(
                model='gemini-2.0-flash',
                contents=f"[SYSTEM]\n{SYSTEM_PROMPT}\n\n[USER]\n{prompt}",
                config=genai_types.GenerateContentConfig(
                    tools=[genai_types.GoogleSearchRetrieval()],
                    temperature=0.3,
                    max_output_tokens=1000,
                ),
            )
            text = response.text

            # Log grounding metadata (sources used)
            if hasattr(response, 'grounding_metadata') and response.grounding_metadata:
                gm = response.grounding_metadata
                if gm.grounding_chunks:
                    sources = [c.uri for c in gm.grounding_chunks[:3] if c.uri]
                    if sources:
                        print(f"   🔍 Search grounding used {len(sources)} web sources")

            return self._check_output_quality(text)
        except Exception as e:
            print(f"⚠️  Google Search grounding failed: {e}")
            return ""

    def sentiment(self, text: str) -> dict:
        if not HF_KEY or not text.strip():
            return {"neutral": 1.0}
        API_URL = "https://api-inference.huggingface.co/models/ProsusAI/finbert"
        headers = {"Authorization": f"Bearer {HF_KEY}"}
        text    = text[:500]
        for attempt in range(3):
            try:
                resp = requests.post(
                    API_URL, headers=headers,
                    json={"inputs": text}, timeout=30,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    if result and isinstance(result[0], list):
                        return {r["label"]: round(r["score"], 3)
                                for r in result[0]}
                elif resp.status_code == 503:
                    print(f"⏳ FinBERT loading (attempt {attempt+1})...")
                    time.sleep(20)
                else:
                    break
            except Exception as e:
                print(f"⚠️  FinBERT error: {e}")
                time.sleep(5)
        return {"neutral": 1.0}

    @staticmethod
    def morning_brief_prompt(index_data: dict, news_items: list = None, consensus_sentiment: str = "neutral") -> str:
        lines = []
        for country, d in index_data.items():
            if d.get("ok"):
                sign = "+" if d.get("change_pct", 0) >= 0 else ""
                lines.append(
                    f"{d.get('flag','')} {country}: "
                    f"{sign}{d.get('change_pct',0):.2f}% [{d.get('status','?')}]"
                )

        # Format validated news with trust scores
        news_block = ""
        if news_items:
            news_lines = []
            for n in news_items[:5]:
                trust = n.get("trust_score", 0)
                source = n.get("source", "unknown")
                headline = n.get("headline", "")[:80]
                news_lines.append(f"• {headline} (Source: {source}, Trust: {trust}/10)")
            if news_lines:
                news_block = f"\nTop headlines (filtered by trust score):\n{chr(10).join(news_lines)}\n"

        return f"""
Today's global equity snapshot:
{chr(10).join(lines)}
{news_block}

Market sentiment consensus: {consensus_sentiment.upper()}

Write a morning market brief. Rules:
- Every claim must cite a specific number (%, ₹Cr, price level)
- Reference actual headlines from the news above
- No generic statements ("markets are mixed" is banned)
- Be direct — what happened, what it means, what to do
- Max 200 words

Structure:
1. 📊 [One number that captures today — pick the most important]
2. 🌍 Global News: 3-4 editorial bullets with ⦿ prefix, each citing a specific data point from the indices/headlines
3. 🇮🇳 India News: 2-3 editorial bullets with ⦿ prefix, what this means for Nifty
4. 📈 Market Impact: What this means for Nifty today — be specific (gap expected? key level?)
5. ⚠️ Risk: One thing that could go wrong
6. 🎯 Watch: One trigger level or event to monitor
"""

    @staticmethod
    def stock_analysis_prompt(symbol: str, data: dict, news: list, tech_context: dict = None) -> str:
        # Format news with trust scores and sentiment
        if news:
            news_lines = []
            for n in news[:5]:
                headline = n.get("headline", "")[:60]
                trust = n.get("trust_score", 0)
                source = n.get("source", "unknown")
                sent = n.get("sentiment", {})
                sent_label = max(sent, key=sent.get) if sent else "neutral"
                news_lines.append(f"• {headline} ({source}, Trust:{trust}/10, {sent_label})")
            news_text = "\n".join(news_lines)
        else:
            news_text = "No recent news."

        vol_note = "🚨 VOLUME SPIKE" if data.get("volume_spike") else "Normal"

        # Format technical context
        tech_block = ""
        if tech_context:
            ma20 = tech_context.get("ma20", 0)
            price = tech_context.get("price", 0)
            ma_diff = ((price - ma20) / ma20 * 100) if ma20 > 0 else 0
            ma_status = "Above" if ma_diff > 0 else "Below"
            tech_block = f"""
Technical context (from 1-month data):
• Price vs 20D SMA: {ma_status} ({ma_diff:+.1f}%)
• 5-day momentum: {tech_context.get('momentum_5d', 'N/A')}
• Monthly return: {tech_context.get('monthly_return', 0):+.2f}%
"""

        return f"""
Analyze {symbol}:
Price: {data.get('price','N/A')}
Day Change: {data.get('day_change',0):+.2f}%
Volume: {data.get('volume',0):,} vs Avg {data.get('avg_volume',0):,} → {vol_note}
7D Range: {data.get('week_low')} to {data.get('week_high')}
1M Range: {data.get('month_low')} to {data.get('month_high')}
{tech_block}
News (weighted by trust score):
{news_text}

5 bullets:
1. Trend: Bullish/Bearish/Neutral + reason (consider technicals)
2. Key Levels: Support and Resistance
3. News Impact: Positive/Negative/Neutral (weight high-trust sources)
4. Signal: BUY / SELL / HOLD / WATCH
5. Risk: Low/Medium/High + main risk

Use trust scores to weight news reliability. Consider technicals in your trend assessment.
"""

    @staticmethod
    def eod_summary_prompt(watchlist_data: dict, news_items: list = None, consensus_sentiment: str = "neutral") -> str:
        lines = []
        for sym, d in watchlist_data.items():
            if d.get("ok"):
                spike = " spike" if d.get("volume_spike") else ""
                lines.append(
                    f"{sym}: {d.get('day_change',0):+.2f}%{spike}"
                )

        # Format validated news
        news_block = ""
        if news_items:
            news_lines = []
            for n in news_items[:5]:
                headline = n.get("headline", "")[:70]
                trust = n.get("trust_score", 0)
                source = n.get("source", "unknown")
                news_lines.append(f"• {headline} ({source}, Trust:{trust}/10)")
            if news_lines:
                news_block = f"\nToday's validated news:\n{chr(10).join(news_lines)}\n"

        return f"""
End-of-day watchlist:
{chr(10).join(lines) if lines else 'No data'}
{news_block}

Market sentiment: {consensus_sentiment.upper()}

Provide (base on actual news, not speculation):
1. Top winner and loser today
2. Overall market mood (reference news sentiment)
3. What patterns/levels to watch (not "overnight events")
4. One trade idea for tomorrow with rationale

Under 200 words. Do NOT invent events. Use the news provided.
"""

    @staticmethod
    def midday_market_prompt(global_indices: dict, top_movers: dict,
                             news_items: list = None, bull_bear: dict = None) -> str:
        # Format global indices (top 5 by absolute change)
        idx_lines = []
        if global_indices:
            sorted_idx = sorted(
                [(c, d) for c, d in global_indices.items() if d.get("ok")],
                key=lambda x: abs(x[1].get("change_pct", 0)),
                reverse=True
            )
            for country, d in sorted_idx[:5]:
                sign = "+" if d.get("change_pct", 0) >= 0 else ""
                idx_lines.append(f"{d.get('flag','')} {country}: {sign}{d.get('change_pct',0):.2f}%")

        # Format top movers
        gainers, losers = [], []
        if top_movers:
            for m in top_movers.get("india", {}).get("gainers", [])[:3]:
                gainers.append(f"{m['symbol']} +{m['change_pct']:.1f}%")
            for m in top_movers.get("india", {}).get("losers", [])[:3]:
                losers.append(f"{m['symbol']} {m['change_pct']:.1f}%")

        # Format news
        news_block = ""
        if news_items:
            news_lines = []
            for n in news_items[:3]:
                headline = n.get("headline", "")[:60]
                trust = n.get("trust_score", 0)
                source = n.get("source", "unknown")
                news_lines.append(f"• {headline} ({source}, Trust:{trust}/10)")
            if news_lines:
                news_block = f"\nHeadlines:\n{chr(10).join(news_lines)}"

        # Bull/bear context
        bb_line = ""
        if bull_bear and bull_bear.get("ok"):
            bb_line = f"\nBull/Bear Score: {bull_bear.get('score', 'N/A')}/100 ({bull_bear.get('label', 'N/A')})"

        return f"""
Midday market snapshot:
Global indices: {chr(10).join(idx_lines) if idx_lines else 'No data'}
Top gainers: {' | '.join(gainers) if gainers else 'No data'}
Top losers: {' | '.join(losers) if losers else 'No data'}
{news_block}
{bb_line}

Provide a sharp 3-point midday brief:
1. Market Mood — what's driving sentiment right now
2. What Changed — any shift since morning (flows, global moves, news)
3. What to Watch — key level or event for the afternoon session

Under 80 words. No disclaimers. Be direct.
"""

    @staticmethod
    def eod_market_prompt(top_movers: dict, global_indices: dict = None,
                          news_items: list = None, consensus_sentiment: str = "neutral",
                          bull_bear: dict = None) -> str:
        # Format top movers (India + US)
        india_g, india_l, us_g, us_l = [], [], [], []
        if top_movers:
            for m in top_movers.get("india", {}).get("gainers", [])[:5]:
                india_g.append(f"{m['symbol']} +{m['change_pct']:.1f}%")
            for m in top_movers.get("india", {}).get("losers", [])[:5]:
                india_l.append(f"{m['symbol']} {m['change_pct']:.1f}%")
            for m in top_movers.get("us", {}).get("gainers", [])[:5]:
                us_g.append(f"{m['symbol']} +{m['change_pct']:.1f}%")
            for m in top_movers.get("us", {}).get("losers", [])[:5]:
                us_l.append(f"{m['symbol']} {m['change_pct']:.1f}%")

        # Format global indices
        idx_lines = []
        if global_indices:
            for country, d in list(global_indices.items())[:8]:
                if d.get("ok"):
                    sign = "+" if d.get("change_pct", 0) >= 0 else ""
                    idx_lines.append(f"{d.get('flag','')} {country}: {sign}{d.get('change_pct',0):.2f}%")

        # Format news
        news_block = ""
        if news_items:
            news_lines = []
            for n in news_items[:5]:
                headline = n.get("headline", "")[:70]
                trust = n.get("trust_score", 0)
                source = n.get("source", "unknown")
                news_lines.append(f"• {headline} ({source}, Trust:{trust}/10)")
            if news_lines:
                news_block = f"\nToday's validated news:\n{chr(10).join(news_lines)}"

        # Bull/bear context
        bb_line = ""
        if bull_bear and bull_bear.get("ok"):
            bb_line = f"\nBull/Bear Score: {bull_bear.get('score', 'N/A')}/100 ({bull_bear.get('label', 'N/A')})"

        return f"""
End-of-day market summary:

Global indices:
{chr(10).join(idx_lines) if idx_lines else 'No data'}

India top gainers: {' | '.join(india_g) if india_g else 'No data'}
India top losers: {' | '.join(india_l) if india_l else 'No data'}
US top gainers: {' | '.join(us_g) if us_g else 'No data'}
US top losers: {' | '.join(us_l) if us_l else 'No data'}

Sentiment: {consensus_sentiment.upper()}
{news_block}
{bb_line}

Provide (based on actual data, not speculation):
1. What happened today + why (reference news and flows)
2. Sector rotation story (which sectors led/lagged)
3. What to watch tomorrow

Under 150 words. Reference news trust scores. No disclaimers.
"""

    @staticmethod
    def market_open_prompt(global_indices: dict, top_movers: dict,
                           news_items: list = None, bull_bear: dict = None) -> str:
        # Format global indices (overnight moves)
        idx_lines = []
        if global_indices:
            sorted_idx = sorted(
                [(c, d) for c, d in global_indices.items() if d.get("ok")],
                key=lambda x: abs(x[1].get("change_pct", 0)),
                reverse=True
            )
            for country, d in sorted_idx[:5]:
                sign = "+" if d.get("change_pct", 0) >= 0 else ""
                idx_lines.append(f"{d.get('flag','')} {country}: {sign}{d.get('change_pct',0):.2f}%")

        # Format pre-market movers
        gap_ups, gap_downs = [], []
        if top_movers:
            for m in top_movers.get("india", {}).get("gainers", [])[:3]:
                if m.get("change_pct", 0) >= 1.5:
                    gap_ups.append(f"{m['symbol']} +{m['change_pct']:.1f}%")
            for m in top_movers.get("india", {}).get("losers", [])[:3]:
                if m.get("change_pct", 0) <= -1.5:
                    gap_downs.append(f"{m['symbol']} {m['change_pct']:.1f}%")

        # Format news
        news_block = ""
        if news_items:
            news_lines = []
            for n in news_items[:3]:
                headline = n.get("headline", "")[:60]
                trust = n.get("trust_score", 0)
                source = n.get("source", "unknown")
                news_lines.append(f"• {headline} ({source}, Trust:{trust}/10)")
            if news_lines:
                news_block = f"\nOvernight news:\n{chr(10).join(news_lines)}"

        # Bull/bear context
        bb_line = ""
        if bull_bear and bull_bear.get("ok"):
            bb_line = f"\nBull/Bear Score: {bull_bear.get('score', 'N/A')}/100 ({bull_bear.get('label', 'N/A')})"

        return f"""
Indian market opening at 9:15 AM IST.

Overnight global moves:
{chr(10).join(idx_lines) if idx_lines else 'No data'}

Gap ups: {' | '.join(gap_ups) if gap_ups else 'None'}
Gap downs: {' | '.join(gap_downs) if gap_downs else 'None'}
{news_block}
{bb_line}

Give a sharp 3-point opening brief:
1. Opening Mood + reason (weight high-trust news sources)
2. Sectors to watch today
3. Key Nifty level to watch

Under 100 words. No disclaimers. Reference trust scores.
"""

    @staticmethod
    def weekly_digest_intelligence_prompt(
        scorecard: dict = None, fii_pattern: dict = None,
        regime_shift: dict = None, institutional_signals: dict = None,
        global_indices: dict = None, news_items: list = None,
        bull_bear: dict = None
    ) -> str:
        # Format scorecard
        sc_block = ""
        if scorecard and scorecard.get("ok"):
            sc_block = f"""Prediction Scorecard: {scorecard.get('correct',0)}/{scorecard.get('total',0)} correct ({scorecard.get('accuracy_pct',0):.0f}%)
Best call: {scorecard.get('best_call', 'N/A')}
Worst call: {scorecard.get('worst_call', 'N/A')}"""

        # Format FII pattern
        fii_block = ""
        if fii_pattern and fii_pattern.get("ok"):
            fii_block = f"""FII Weekly: ₹{fii_pattern.get('weekly_net',0):+,.0f} Cr
DII Weekly: ₹{fii_pattern.get('dii_net',0):+,.0f} Cr
Streak: {fii_pattern.get('streak_weeks',0)} weeks"""

        # Format regime shift
        regime_block = ""
        if regime_shift and regime_shift.get("ok"):
            regime_block = f"""Regime: {regime_shift.get('monday_label','N/A')} → {regime_shift.get('friday_label','N/A')}
Score: {regime_shift.get('monday_score','?')} → {regime_shift.get('friday_score','?')}
Key driver: {regime_shift.get('what_changed', 'N/A')}"""

        # Format institutional signals
        inst_block = ""
        if institutional_signals:
            sr = institutional_signals.get("sector_regime", {})
            vs = institutional_signals.get("volatility_setup", {})
            ra = institutional_signals.get("risk_appetite", {})
            bt = institutional_signals.get("breadth_thrust", {})
            fi = institutional_signals.get("fii_footprint", {})
            parts = []
            if sr.get("ok"):
                parts.append(f"Sector Regime: {sr['label']}")
            if vs.get("ok"):
                parts.append(f"Vol Setup: VIX {vs['vix_current']:.1f} ({vs['percentile']}th pctile) — {vs['label']}")
            if ra.get("ok"):
                parts.append(f"Risk Appetite: {ra['label']}")
            if bt.get("ok"):
                parts.append(f"Breadth: {bt['label']}")
            if fi.get("ok"):
                parts.append(f"FII Footprint: {fi['label']}")
            inst_block = "\n".join(parts)

        # Format global indices
        idx_lines = []
        if global_indices:
            for country, d in list(global_indices.items())[:8]:
                if d.get("ok"):
                    sign = "+" if d.get("change_pct", 0) >= 0 else ""
                    idx_lines.append(f"{d.get('flag','')} {country}: {sign}{d.get('change_pct',0):.2f}%")

        # Format news
        news_block = ""
        if news_items:
            news_lines = []
            for n in news_items[:5]:
                headline = n.get("headline", "")[:70]
                trust = n.get("trust_score", 0)
                news_lines.append(f"• {headline} (Trust:{trust}/10)")
            if news_lines:
                news_block = "\n".join(news_lines)

        bb_line = ""
        if bull_bear and bull_bear.get("ok"):
            bb_line = f"Bull/Bear: {bull_bear.get('score','N/A')}/100 ({bull_bear.get('label','N/A')})"

        return f"""
Weekly market intelligence report:

{sc_block}

{fii_block}

{regime_block}

Global indices:
{chr(10).join(idx_lines) if idx_lines else 'No data'}

Institutional signals:
{inst_block if inst_block else 'No data'}

News this week:
{news_block if news_block else 'No data'}

{bb_line}

Provide a sharp weekly narrative:
1. What happened this week + why (reference FII pattern, regime shift, news)
2. What smart money is doing (institutional signals — sector regime, risk appetite, FII footprint)
3. Contrarian opportunity — what's the crowd missing?
4. Next week preview — key events, levels, what to watch

Under 200 words. Be direct. Reference data, not opinions.
"""

    @staticmethod
    def weekly_digest_prompt(index_data: dict, watchlist_data: dict) -> str:
        global_lines = [
            f"{d.get('flag','')} {c}: {d.get('change_pct',0):+.2f}%"
            for c, d in index_data.items() if d.get("ok")
        ]
        watch_lines = [
            f"{s}: {d.get('day_change',0):+.2f}%"
            for s, d in watchlist_data.items() if d.get("ok")
        ]
        return f"""
Weekly Market Digest:
Global: {chr(10).join(global_lines[:10])}
Watchlist: {chr(10).join(watch_lines)}

Weekly brief:
1. This Week's Theme
2. Key Global Story
3. India Standout performer
4. Next Week Outlook
5. Watchlist Focus for next week

Under 250 words.
"""
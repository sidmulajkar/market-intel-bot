"""
AI Engine — Groq + Google AI Studio
Fixed: RateLimitError import + correct model names
"""
import os
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

GROQ_KEY   = os.environ.get('GROQ_API_KEY',  '')
GOOGLE_KEY = os.environ.get('GOOGLE_AI_KEY', '')
HF_KEY     = os.environ.get('HF_KEY',        '')

SYSTEM_PROMPT = (
    "You are a quantitative market analyst. Your output must:\n"
    "- Lead with the single most important number and its historical context\n"
    "- Cite specific numbers with 'since [date]' or 'Xth percentile' context\n"
    "- Provide probability-weighted scenarios (bull/bear/base with %)\n"
    "- Reference cross-signal correlations when active in the data\n"
    "- Never state a number without context (e.g., NOT 'VIX is 18' but 'VIX at 18, 65th percentile of 90D')\n"
    "- Use emojis for visual structure: 📊 📈 🔑 ⚠️ 🟢 🔴\n"
    "- No disclaimers, no padding, no fluff"
)

class AIEngine:

    def __init__(self):
        self.groq_client  = None
        self.google_model = None

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

    def analyze(self, task: str, prompt: str) -> str:
        if task == "fast":
            return (self._try_groq(prompt)
                    or self._try_google(prompt)
                    or "⚠️ AI analysis temporarily unavailable.")
        elif task == "volume":
            return (self._try_google(prompt)
                    or self._try_groq(prompt)
                    or "⚠️ AI analysis temporarily unavailable.")
        else:
            return (self._try_groq(prompt)
                    or self._try_google(prompt)
                    or "⚠️ AI analysis temporarily unavailable.")

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
                return resp.choices[0].message.content

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
                return resp.text
            except Exception as e:
                print(f"⚠️  Google AI error attempt {attempt+1}: {e}")
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
                else:
                    return ""
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

Morning brief required:
1. 🌍 Global Sentiment: Based on headlines above + index moves
2. 🔥 Top 3 Movers: What moved (reference actual news where possible)
3. 🇮🇳 India Impact: What this means for Nifty/Sensex today
4. ⚠️ Key Risk: Top 2 things to watch
5. 🎯 Trade Idea: One actionable opportunity today

Under 200 words. Sharp. No disclaimers. Reference actual news headlines in your analysis.
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
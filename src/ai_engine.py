"""
AI Engine — Smart Router
Groq (speed) → Google AI Studio (volume) → fallback
"""
import os
import time
import requests
from groq import Groq, RateLimitError

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
    "You are a sharp, experienced financial analyst. "
    "Give concise, actionable market insights. "
    "No disclaimers, no padding, no fluff. "
    "Use bullet points with emojis. Max 200 words."
)

class AIEngine:

    def __init__(self):
        self.groq_client  = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
        self.google_model = None
        if GOOGLE_AVAILABLE and GOOGLE_KEY:
            try:
                genai.configure(api_key=GOOGLE_KEY)
                self.google_model = genai.GenerativeModel('gemini-2.5-flash')
            except Exception as e:
                print(f"⚠️  Google AI init failed: {e}")

    def analyze(self, task: str, prompt: str) -> str:
        """
        task = 'fast'   → Groq first
        task = 'volume' → Google first
        task = 'any'    → Groq first with Google fallback
        """
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
                    max_tokens=600,
                    temperature=0.2,
                )
                return resp.choices[0].message.content
            except RateLimitError:
                wait = 30 * (2 ** attempt)
                print(f"⏳ Groq rate limited — waiting {wait}s (attempt {attempt+1}/3)")
                if attempt < 2:
                    time.sleep(wait)
                else:
                    return ""
            except Exception as e:
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
                cfg  = genai.GenerationConfig(max_output_tokens=600, temperature=0.2)
                resp = self.google_model.generate_content(prompt, generation_config=cfg)
                return resp.text
            except Exception as e:
                print(f"⚠️  Google AI error attempt {attempt+1}: {e}")
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
                else:
                    return ""
        return ""

    def sentiment(self, text: str) -> dict:
        """FinBERT sentiment via HuggingFace free API"""
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
                        return {r["label"]: round(r["score"], 3) for r in result[0]}
                elif resp.status_code == 503:
                    print(f"⏳ FinBERT loading (attempt {attempt+1})...")
                    time.sleep(20)
                else:
                    break
            except Exception as e:
                print(f"⚠️  FinBERT error: {e}")
                time.sleep(5)
        return {"neutral": 1.0}

    # ── PROMPT BUILDERS ───────────────────────────────────────────

    @staticmethod
    def morning_brief_prompt(index_data: dict) -> str:
        lines = []
        for country, d in index_data.items():
            if d.get("ok"):
                sign = "+" if d.get("change_pct", 0) >= 0 else ""
                lines.append(
                    f"{d.get('flag','')} {country}: "
                    f"{sign}{d.get('change_pct',0):.2f}% [{d.get('status','?')}]"
                )
        return f"""
Today's global equity snapshot:
{chr(10).join(lines)}

Morning brief required:
1. 🌍 Global Sentiment: [Bullish/Bearish/Mixed] + one-line reason
2. 🔥 Top 3 Movers: What moved + why
3. 🇮🇳 India Impact: What this means for Nifty/Sensex today
4. ⚠️ Key Risk: Top 2 things to watch
5. 🎯 Trade Idea: One actionable opportunity today

Under 200 words. Sharp. No disclaimers.
"""

    @staticmethod
    def stock_analysis_prompt(symbol: str, data: dict, news: list) -> str:
        news_text = "\n".join(
            [f"• {n['headline']} ({n.get('source','')})" for n in news[:5]]
        ) if news else "No recent news."
        vol_note = "🚨 VOLUME SPIKE" if data.get("volume_spike") else "Normal"
        return f"""
Analyze {symbol}:
💰 Price: {data.get('price','N/A')}
📊 Day Change: {data.get('day_change',0):+.2f}%
📈 Volume: {data.get('volume',0):,} vs Avg {data.get('avg_volume',0):,} → {vol_note}
📅 7D Range: {data.get('week_low')} – {data.get('week_high')}
📅 1M Range: {data.get('month_low')} – {data.get('month_high')}

News:
{news_text}

5 bullets exactly:
1. 📈 Trend: [Bullish/Bearish/Neutral] + reason
2. 🎯 Key Levels: Support ___ | Resistance ___
3. 📰 News: [Positive/Negative/Neutral] + why
4. Signal: 🟢 BUY / 🔴 SELL / 🟡 HOLD / 👁 WATCH
5. ⚠️ Risk: [Low/Medium/High] + main risk

No disclaimers. Direct.
"""

    @staticmethod
    def eod_summary_prompt(watchlist_data: dict) -> str:
        lines = []
        for sym, d in watchlist_data.items():
            if d.get("ok"):
                spike = " ⚡" if d.get("volume_spike") else ""
                lines.append(f"• {sym}: {d.get('day_change',0):+.2f}%{spike}")
        return f"""
End-of-day watchlist:
{chr(10).join(lines) if lines else 'No data available'}

Provide:
1. 🏆 Today's top winner + loser (one-liner each)
2. 📊 Overall market mood today
3. 🌙 What to watch overnight
4. 📅 Key events tomorrow
5. 💡 One trade idea for tomorrow

Under 200 words. Sharp.
"""

    @staticmethod
    def weekly_digest_prompt(index_data: dict, watchlist_data: dict) -> str:
        global_lines = [
            f"{d.get('flag','')} {c}: {d.get('change_pct',0):+.2f}%"
            for c, d in index_data.items() if d.get("ok")
        ]
        watch_lines = [
            f"• {s}: {d.get('day_change',0):+.2f}%"
            for s, d in watchlist_data.items() if d.get("ok")
        ]
        return f"""
Weekly Market Digest:

Global Markets:
{chr(10).join(global_lines[:12])}

My Watchlist:
{chr(10).join(watch_lines)}

Strategic weekly brief:
1. 📊 This Week's Theme: Dominant narrative
2. 🌍 Global Story: Key macro development
3. 🇮🇳 India Standout: Best/worst + reason
4. 📅 Next Week: Bullish/Bearish/Mixed + reason
5. 🎯 Watchlist Focus: 2-3 stocks for next week

Under 250 words. Strategic.
"""
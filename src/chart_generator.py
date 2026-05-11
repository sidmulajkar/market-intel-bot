"""
Technical Chart Generator
Generates candlestick + RSI + Volume charts
Returns BytesIO PNG ready for Telegram
"""
import io
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from datetime import datetime
import pytz
import yfinance as yf
import ta

def _fetch_ohlcv(symbol: str, period: str = "1mo") -> pd.DataFrame:
    try:
        t  = yf.Ticker(symbol)
        df = t.history(period=period, interval="1d")
        return df.dropna(subset=["Close"])
    except Exception as e:
        print(f"⚠️  Chart data fetch failed ({symbol}): {e}")
        return pd.DataFrame()

def generate_technical_chart(symbol: str, period: str = "1mo") -> io.BytesIO:
    """
    Generate technical analysis chart with:
    - Candlestick price action
    - SMA 20 + SMA 50
    - RSI (14)
    - Volume bars
    Returns BytesIO PNG.
    """
    df = _fetch_ohlcv(symbol, period=period)
    if df.empty or len(df) < 5:
        return _generate_error_chart(symbol)

    df["SMA20"] = ta.trend.sma_indicator(df["Close"], window=min(20, len(df)))
    if len(df) >= 50:
        df["SMA50"] = ta.trend.sma_indicator(df["Close"], window=50)
    else:
        df["SMA50"] = np.nan

    df["RSI"] = ta.momentum.rsi(df["Close"], window=min(14, len(df) - 1))

    plt.style.use("dark_background")
    fig = plt.figure(figsize=(12, 8), facecolor="#0d0d0d")
    gs  = GridSpec(3, 1, figure=fig, height_ratios=[3, 1, 1], hspace=0.08)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax3 = fig.add_subplot(gs[2], sharex=ax1)

    x = range(len(df))

    for i, (idx, row) in enumerate(df.iterrows()):
        color = "#00c851" if row["Close"] >= row["Open"] else "#ff4444"
        ax1.bar(i, abs(row["Close"] - row["Open"]),
                bottom=min(row["Open"], row["Close"]),
                color=color, width=0.7, linewidth=0)
        ax1.plot([i, i], [row["Low"], row["High"]],
                 color=color, linewidth=0.8)

    ax1.plot(x, df["SMA20"].values, color="#ffaa00",
             linewidth=1.5, label="SMA 20", alpha=0.9)
    if not df["SMA50"].isna().all():
        ax1.plot(x, df["SMA50"].values, color="#00aaff",
                 linewidth=1.5, label="SMA 50", alpha=0.9)

    pad = (df["High"].max() - df["Low"].min()) * 0.05
    ax1.set_ylim(df["Low"].min() - pad, df["High"].max() + pad)
    ax1.set_facecolor("#0d0d0d")
    ax1.tick_params(colors="#888888", labelsize=8)
    ax1.set_ylabel("Price", color="#888888", fontsize=9)
    ax1.legend(loc="upper left", fontsize=8,
               facecolor="#1a1a1a", edgecolor="#333333")
    ax1.grid(color="#222222", linestyle="--", linewidth=0.5)

    ist     = datetime.now(pytz.timezone("Asia/Kolkata"))
    last_px = df["Close"].iloc[-1]
    day_chg = ((df["Close"].iloc[-1] - df["Close"].iloc[-2]) /
               df["Close"].iloc[-2] * 100) if len(df) >= 2 else 0
    sign    = "+" if day_chg >= 0 else ""
    t_color = "#00c851" if day_chg >= 0 else "#ff4444"
    ax1.set_title(
        f"{symbol}  ₹{last_px:,.2f}  {sign}{day_chg:.2f}%   "
        f"[{period.upper()}]   {ist.strftime('%d %b %Y %H:%M IST')}",
        color=t_color, fontsize=11, pad=8, fontweight="bold",
    )

    ax2.plot(x, df["RSI"].values, color="#aa44ff", linewidth=1.3)
    ax2.axhline(70, color="#ff4444", linewidth=0.8, linestyle="--", alpha=0.7)
    ax2.axhline(30, color="#00c851", linewidth=0.8, linestyle="--", alpha=0.7)
    ax2.fill_between(x, df["RSI"].values, 70,
                     where=(df["RSI"].values >= 70),
                     color="#ff4444", alpha=0.15)
    ax2.fill_between(x, df["RSI"].values, 30,
                     where=(df["RSI"].values <= 30),
                     color="#00c851", alpha=0.15)
    ax2.set_ylim(0, 100)
    ax2.set_facecolor("#0d0d0d")
    ax2.tick_params(colors="#888888", labelsize=7)
    ax2.set_ylabel("RSI", color="#888888", fontsize=8)
    ax2.grid(color="#222222", linestyle="--", linewidth=0.4)

    vol_colors = [
        "#00c851" if row["Close"] >= row["Open"] else "#ff4444"
        for _, row in df.iterrows()
    ]
    ax3.bar(x, df["Volume"].values, color=vol_colors, width=0.7, alpha=0.8)
    ax3.set_facecolor("#0d0d0d")
    ax3.tick_params(colors="#888888", labelsize=7)
    ax3.set_ylabel("Volume", color="#888888", fontsize=8)
    ax3.grid(color="#222222", linestyle="--", linewidth=0.4)

    tick_step      = max(1, len(df) // 8)
    tick_positions = list(range(0, len(df), tick_step))
    tick_labels    = [df.index[i].strftime("%d %b") for i in tick_positions]
    ax3.set_xticks(tick_positions)
    ax3.set_xticklabels(tick_labels, color="#888888", fontsize=7,
                         rotation=30, ha="right")
    plt.setp(ax1.get_xticklabels(), visible=False)
    plt.setp(ax2.get_xticklabels(), visible=False)

    fig.text(0.99, 0.01, "AI Market Intel Bot",
             ha="right", va="bottom", color="#333333",
             fontsize=8, style="italic")

    plt.tight_layout(pad=1.0)
    buf      = io.BytesIO()
    buf.name = f"chart_{symbol}.png"
    fig.savefig(buf, format="png", dpi=130,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf

def _generate_error_chart(symbol: str) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(6, 2), facecolor="#0d0d0d")
    ax.text(0.5, 0.5, f"No chart data available for {symbol}",
            ha="center", va="center", color="white", fontsize=12,
            transform=ax.transAxes)
    ax.set_facecolor("#0d0d0d")
    ax.axis("off")
    buf = io.BytesIO()
    buf.name = f"chart_{symbol}_error.png"
    fig.savefig(buf, format="png", dpi=80, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf
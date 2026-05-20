"""
Technical Analysis — Pre-compute levels and indicators from OHLCV data
Zero API cost — uses existing close_series from yfinance.
"""
from typing import Dict, List, Optional


def compute_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """
    Compute RSI (Relative Strength Index) from close prices.
    Returns: RSI value (0-100), or None if insufficient data.
    """
    if len(closes) < period + 1:
        return None

    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = changes[-(period):]

    gains = [c for c in recent if c > 0]
    losses = [-c for c in recent if c < 0]

    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def compute_moving_averages(closes: List[float]) -> Dict:
    """
    Compute key moving averages from close prices.
    Returns: dict with 50-DMA, 200-DMA, 20-DMA and their distances from current price.
    """
    if not closes:
        return {}

    current = closes[-1]
    result = {"current": current}

    if len(closes) >= 20:
        ma20 = sum(closes[-20:]) / 20
        result["ma20"] = round(ma20, 2)
        result["ma20_dist_pct"] = round(((current - ma20) / ma20) * 100, 2)

    if len(closes) >= 50:
        ma50 = sum(closes[-50:]) / 50
        result["ma50"] = round(ma50, 2)
        result["ma50_dist_pct"] = round(((current - ma50) / ma50) * 100, 2)

    if len(closes) >= 200:
        ma200 = sum(closes[-200:]) / 200
        result["ma200"] = round(ma200, 2)
        result["ma200_dist_pct"] = round(((current - ma200) / ma200) * 100, 2)

    return result


def compute_support_resistance(closes: List[float], lookback: int = 60) -> Dict:
    """
    Compute support and resistance levels from recent price action.
    Uses swing highs/lows and round number proximity.
    Returns: nearest support and resistance levels.
    """
    if len(closes) < 10:
        return {}

    current = closes[-1]
    recent = closes[-lookback:] if len(closes) >= lookback else closes

    # Find swing highs (local maxima) and swing lows (local minima)
    swing_highs = []
    swing_lows = []

    for i in range(2, len(recent) - 2):
        # Swing high: higher than 2 neighbors on each side
        if (recent[i] > recent[i-1] and recent[i] > recent[i-2] and
            recent[i] > recent[i+1] and recent[i] > recent[i+2]):
            swing_highs.append(recent[i])
        # Swing low: lower than 2 neighbors on each side
        if (recent[i] < recent[i-1] and recent[i] < recent[i-2] and
            recent[i] < recent[i+1] and recent[i] < recent[i+2]):
            swing_lows.append(recent[i])

    # Nearest resistance: closest swing high above current price
    resistance_levels = sorted([h for h in swing_highs if h > current])
    support_levels = sorted([l for l in swing_lows if l < current], reverse=True)

    result = {}
    if resistance_levels:
        result["resistance_1"] = round(resistance_levels[0], 0)
        if len(resistance_levels) > 1:
            result["resistance_2"] = round(resistance_levels[1], 0)
    if support_levels:
        result["support_1"] = round(support_levels[0], 0)
        if len(support_levels) > 1:
            result["support_2"] = round(support_levels[1], 0)

    # Round number proximity (psychological levels)
    if current > 0:
        round_step = 500 if current > 5000 else 100 if current > 1000 else 50
        nearest_round = round(current / round_step) * round_step
        result["psychological_level"] = nearest_round

    return result


def compute_macd(closes: List[float]) -> Dict:
    """
    Compute MACD (12, 26, 9) from close prices.
    Returns: MACD line, signal line, histogram, and crossover status.
    """
    if len(closes) < 35:  # Need at least 26 + 9 for signal
        return {}

    def ema(data: List[float], period: int) -> List[float]:
        multiplier = 2 / (period + 1)
        ema_values = [sum(data[:period]) / period]
        for price in data[period:]:
            ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
        return ema_values

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)

    # Align lengths (EMA12 starts at index 11, EMA26 at index 25)
    # MACD line = EMA12 - EMA26 (starting from index 25)
    min_len = min(len(ema12), len(ema26))
    offset12 = len(ema12) - min_len
    offset26 = len(ema26) - min_len

    macd_line = [ema12[offset12 + i] - ema26[offset26 + i] for i in range(min_len)]

    if len(macd_line) < 9:
        return {}

    # Signal line = 9-period EMA of MACD line
    signal_line = ema(macd_line, 9)

    if not signal_line:
        return {}

    macd_val = macd_line[-1]
    signal_val = signal_line[-1]
    histogram = macd_val - signal_val

    # Crossover detection
    if len(macd_line) >= 2 and len(signal_line) >= 2:
        prev_macd = macd_line[-2]
        prev_signal = signal_line[-2]
        if prev_macd <= prev_signal and macd_val > signal_val:
            crossover = "BULLISH CROSS"
        elif prev_macd >= prev_signal and macd_val < signal_val:
            crossover = "BEARISH CROSS"
        else:
            crossover = None
    else:
        crossover = None

    result = {
        "macd": round(macd_val, 2),
        "signal": round(signal_val, 2),
        "histogram": round(histogram, 2),
    }
    if crossover:
        result["crossover"] = crossover

    return result


def compute_bollinger_bands(closes: List[float], period: int = 20, std_dev: float = 2.0) -> Dict:
    """
    Compute Bollinger Bands from close prices.
    Returns: upper band, middle band, lower band, bandwidth, %B.
    """
    if len(closes) < period:
        return {}

    recent = closes[-period:]
    middle = sum(recent) / period
    variance = sum((x - middle) ** 2 for x in recent) / period
    std = variance ** 0.5

    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)

    current = closes[-1]
    bandwidth = ((upper - lower) / middle) * 100 if middle > 0 else 0
    percent_b = ((current - lower) / (upper - lower)) * 100 if (upper - lower) > 0 else 50

    return {
        "upper": round(upper, 2),
        "middle": round(middle, 2),
        "lower": round(lower, 2),
        "bandwidth": round(bandwidth, 2),
        "percent_b": round(percent_b, 1),
    }


def compute_full_analysis(closes: List[float], symbol: str = "") -> Dict:
    """
    Run all technical analysis on a close price series.
    Returns: complete technical picture for a symbol.
    """
    if not closes or len(closes) < 5:
        return {"ok": False}

    result = {
        "ok": True,
        "symbol": symbol,
        "current": closes[-1],
    }

    # Moving averages
    ma = compute_moving_averages(closes)
    result.update(ma)

    # RSI
    rsi = compute_rsi(closes)
    if rsi is not None:
        result["rsi"] = rsi
        if rsi >= 70:
            result["rsi_label"] = "OVERBOUGHT"
        elif rsi <= 30:
            result["rsi_label"] = "OVERSOLD"
        else:
            result["rsi_label"] = "NEUTRAL"

    # Support/Resistance
    sr = compute_support_resistance(closes)
    result.update(sr)

    # MACD
    macd = compute_macd(closes)
    if macd:
        result["macd"] = macd

    # Bollinger Bands
    bb = compute_bollinger_bands(closes)
    if bb:
        result["bollinger"] = bb

    return result


def format_technical_analysis(analysis: Dict) -> str:
    """
    Format technical analysis for AI prompt injection.
    Returns: concise technical summary with key levels.
    """
    if not analysis.get("ok"):
        return ""

    symbol = analysis.get("symbol", "")
    lines = []

    # Moving averages
    ma_parts = []
    if "ma200" in analysis:
        ma_parts.append(f"200-DMA: {analysis['ma200']:,.0f} ({analysis['ma200_dist_pct']:+.1f}%)")
    if "ma50" in analysis:
        ma_parts.append(f"50-DMA: {analysis['ma50']:,.0f} ({analysis['ma50_dist_pct']:+.1f}%)")
    if "ma20" in analysis:
        ma_parts.append(f"20-DMA: {analysis['ma20']:,.0f} ({analysis['ma20_dist_pct']:+.1f}%)")
    if ma_parts:
        lines.append("MA: " + " | ".join(ma_parts))

    # RSI
    if "rsi" in analysis:
        lines.append(f"RSI(14): {analysis['rsi']} ({analysis['rsi_label']})")

    # Support/Resistance
    sr_parts = []
    if "support_1" in analysis:
        sr_parts.append(f"Support: {analysis['support_1']:,.0f}")
    if "support_2" in analysis:
        sr_parts.append(f"Support 2: {analysis['support_2']:,.0f}")
    if "resistance_1" in analysis:
        sr_parts.append(f"Resistance: {analysis['resistance_1']:,.0f}")
    if "resistance_2" in analysis:
        sr_parts.append(f"Resistance 2: {analysis['resistance_2']:,.0f}")
    if "psychological_level" in analysis:
        sr_parts.append(f"Psych level: {analysis['psychological_level']:,.0f}")
    if sr_parts:
        lines.append("Levels: " + " | ".join(sr_parts))

    # MACD
    if "macd" in analysis:
        macd = analysis["macd"]
        macd_str = f"MACD: {macd['macd']:+.2f} (signal: {macd['signal']:+.2f})"
        if "crossover" in macd:
            macd_str += f" 🔔 {macd['crossover']}"
        lines.append(macd_str)

    # Bollinger
    if "bollinger" in analysis:
        bb = analysis["bollinger"]
        bb_pos = "near upper" if bb["percent_b"] > 80 else "near lower" if bb["percent_b"] < 20 else "middle"
        lines.append(f"BB: upper {bb['upper']:,.0f} | lower {bb['lower']:,.0f} ({bb_pos}, %B: {bb['percent_b']})")

    if not lines:
        return ""

    header = f"[Technical: {symbol}]" if symbol else "[Technical]"
    return header + "\n" + "\n".join(lines)

"""
Historical Clone Engine (T4.2 / G3)
6D India macro state vector + 5D Global macro state vector.
Both use Euclidean nearest-neighbor → empirical forward returns.
Zero speculation. Python computes conclusions.
"""
from datetime import datetime, timedelta
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from src.db import get_client, get_fii_dii_flows

# ── Constants ──────────────────────────────────────────────────────────
MACRO_TICKERS: Dict[str, str] = {
    "vix": "^INDIAVIX",
    "usdinr": "USDINR=X",
    "brent": "BZ=F",
    "dxy": "DX-Y.NYB",
}

CLONE_VARS: List[str] = ["vix", "usdinr", "brent", "dxy", "fii_5d", "pcr"]
WEIGHTS: List[float] = [0.20, 0.20, 0.15, 0.15, 0.20, 0.10]
NIFTY_TICKER: str = "^NSEI"
YF_PERIOD: str = "5y"
MIN_ROLLING: int = 126

# ── G3 Global Clone Constants ──────────────────────────────────────────
GLOBAL_TICKERS: Dict[str, str] = {
    "dxy": "DX-Y.NYB",
    "us_10y": "^TNX",
    "hyg": "HYG",
    "gold": "GC=F",
    "copper": "HG=F",
    "usdjpy": "JPY=X",
}

GLOBAL_CLONE_VARS: List[str] = ["dxy", "us_10y", "hyg", "cu_au_ratio", "usdjpy"]
GLOBAL_WEIGHTS: List[float] = [0.25, 0.20, 0.20, 0.20, 0.15]
GLOBAL_NIFTY_TICKER: str = "^NSEI"
SPY_TICKER: str = "SPY"
EEM_TICKER: str = "EEM"


# ── Data Fetching ──────────────────────────────────────────────────────

# CSV column → clone engine key mapping
_CSV_COL_MAP: Dict[str, str] = {
    "IndiaVIX": "vix",
    "USDINR": "usdinr",
    "Brent": "brent",
    "DXY": "dxy",
    "US10Y": "us_10y",
    "HYG": "hyg",
    "Gold": "gold",
    "Copper": "copper",
    "USDJPY": "usdjpy",
}
_REVERSE_MAP: Dict[str, str] = {v: k for k, v in _CSV_COL_MAP.items()}


def _fetch_csv_history(ticker_map: Dict[str, str]) -> pd.DataFrame:
    """Fetch history from anchor_history.csv. Zero yfinance calls. Instant.
    
    Returns DataFrame with same key names as _fetch_yfinance would produce.
    Falls back to yfinance for tickers not in CSV (forward return tickers).
    """
    from src.csv_data import load_history
    df = load_history("anchors")
    if df.empty:
        return pd.DataFrame()
    
    series_list = []
    for key, t in ticker_map.items():
        csv_col = _REVERSE_MAP.get(key)
        if csv_col and csv_col in df.columns:
            s = df[csv_col].dropna().rename(key)
            s.index = pd.to_datetime(s.index.date)  # tz-naive for matching
            series_list.append(s)
    
    if not series_list:
        return pd.DataFrame()
    return pd.concat(series_list, axis=1).sort_index()


def _fetch_nifty_csv() -> pd.DataFrame:
    """Fetch Nifty history from nifty_history.csv. Zero yfinance calls."""
    from src.csv_data import load_history
    df = load_history("nifty")
    if df.empty or "Close" not in df.columns:
        return pd.DataFrame()
    s = df["Close"].dropna().rename(NIFTY_TICKER)
    s.index = pd.to_datetime(s.index.date)  # tz-naive for matching
    return pd.DataFrame({NIFTY_TICKER: s}).sort_index()


def _fetch_yfinance(tickers: Dict[str, str]) -> pd.DataFrame:
    """Fetch daily close history for multiple yfinance tickers. Merges on date index."""
    series_list: List[pd.Series] = []
    for key, t in tickers.items():
        try:
            hist = yf.Ticker(t).history(period=YF_PERIOD, auto_adjust=True)
            if hist.empty:
                continue
            s = hist["Close"].rename(key)
            s.index = pd.to_datetime(s.index.date)
            series_list.append(s)
        except Exception:
            continue
    if not series_list:
        return pd.DataFrame()
    return pd.concat(series_list, axis=1)


def _fetch_fii_5d_history(days: int = 630) -> pd.DataFrame:
    """Fetch FII flows from Supabase and compute 5D cumulative sums."""
    flows = get_fii_dii_flows(days=days) or []
    if not flows:
        return pd.DataFrame()
    records = []
    for f in flows:
        d = f.get("date")
        val = f.get("fiinet_cr")
        if d and val is not None:
            records.append({"date": d, "fiinet_cr": float(val)})
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    df["fii_5d"] = df["fiinet_cr"].rolling(5, min_periods=3).sum()
    return df[["fii_5d"]]


def _fetch_pcr_history(days: int = 630) -> pd.DataFrame:
    """Fetch NIFTY put-call ratio history from options_snapshots."""
    try:
        client = get_client()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        resp = client.table("options_snapshots")\
            .select("created_at, pcr")\
            .eq("symbol", "NIFTY")\
            .eq("run", "morning")\
            .gte("created_at", cutoff)\
            .order("created_at", desc=False)\
            .execute()
        rows = resp.data if resp and resp.data else []
        records = []
        for r in rows:
            d = (r.get("created_at") or "")[:10]
            p = r.get("pcr")
            if d and p is not None:
                records.append({"date": d, "pcr": float(p)})
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df = df.drop_duplicates("date").sort_values("date").set_index("date")
        return df[["pcr"]]
    except Exception as e:
        print(f"   ⚠️ PCR history fetch: {e}")
        return pd.DataFrame()


def get_current_fii_5d(days: int = 10) -> Optional[float]:
    """Fetch current 5-day cumulative FII flow from Supabase."""
    flows = get_fii_dii_flows(days=days) or []
    if not flows:
        return None
    vals = [f.get("fiinet_cr") for f in flows if f.get("fiinet_cr") is not None]
    vals = vals[-5:]
    if len(vals) < 3:
        return None
    return sum(vals)


def _compute_forward_returns(
    nifty_series: pd.Series,
    clone_date: str,
    horizon: int = 30,
) -> Dict[str, Optional[float]]:
    """Compute forward return and max drawdown for Nifty after clone_date."""
    if nifty_series.empty:
        return {"return_pct": None, "max_dd": None}
    try:
        dt = pd.Timestamp(clone_date)
        if dt not in nifty_series.index:
            return {"return_pct": None, "max_dd": None}
        entry = nifty_series.loc[dt]
        mask = (nifty_series.index > dt) & (
            nifty_series.index <= dt + timedelta(days=horizon * 2)
        )
        forward = nifty_series[mask].iloc[:horizon]
        if len(forward) < 10:
            return {"return_pct": None, "max_dd": None}
        ret = round((forward.iloc[-1] / entry - 1) * 100, 1)
        dd = round((forward.min() / entry - 1) * 100, 1)
        return {"return_pct": ret, "max_dd": dd}
    except Exception:
        return {"return_pct": None, "max_dd": None}


# ── Core Engine ───────────────────────────────────────────────────────

def find_clones(
    current_vix: float,
    current_usdinr: float,
    current_brent: float,
    current_dxy: float,
    current_fii_5d: Optional[float] = None,
    current_pcr: Optional[float] = None,
    trade_date: Optional[str] = None,
    top_n: int = 3,
    exclude_recent: int = 30,
    min_history: int = 252,
) -> Dict[str, Any]:
    """Find top-N historical clones via Euclidean distance on 6D percentile vectors.

    Parameters are current-day macro state values — caller provides from
    state.macro / state.derivatives / flow_metrics.

    Returns:
        status: "ok" | "insufficient_data"
        clones: list of {date, distance, nifty_30d_fwd, max_dd}
        current_pctiles: dict of variable→percentile
    """
    trade_date_str = trade_date or datetime.now().strftime("%Y-%m-%d")
    cutoff_dt = pd.Timestamp(trade_date_str) - timedelta(days=exclude_recent)
    cutoff_date = cutoff_dt.strftime("%Y-%m-%d")

    # 1. Fetch all history — CSV-first for macro + nifty, Supabase for FII/PCR
    macro_df = _fetch_csv_history(MACRO_TICKERS)
    if macro_df.empty:
        macro_df = _fetch_yfinance(MACRO_TICKERS)
    fii_df = _fetch_fii_5d_history(days=min_history + 90) if current_fii_5d is not None else pd.DataFrame()
    pcr_df = _fetch_pcr_history(days=min_history + 90) if current_pcr is not None else pd.DataFrame()
    nifty_df = _fetch_nifty_csv()
    if nifty_df.empty:
        nifty_df = _fetch_yfinance({NIFTY_TICKER: NIFTY_TICKER})

    # 2. Merge into single DataFrame
    merged = macro_df.join(fii_df, how="outer").join(pcr_df, how="outer")
    if merged.empty or len([c for c in CLONE_VARS if c in merged.columns and merged[c].notna().sum() > MIN_ROLLING]) < 2:
        return {"status": "insufficient_data", "clones": [], "current_pctiles": {}}

    # 3. Trim to reasonable window (min_history + buffer for percentile calc)
    if len(merged) > min_history + 120:
        merged = merged.iloc[-(min_history + 120):]

    # 4. Build current percentile vector — each variable's latest value vs its full history
    actual = {
        "vix": current_vix,
        "usdinr": current_usdinr,
        "brent": current_brent,
        "dxy": current_dxy,
        "fii_5d": current_fii_5d,
        "pcr": current_pcr,
    }
    current_pctiles: Dict[str, float] = {}
    for var in CLONE_VARS:
        val = actual.get(var)
        if val is None or var not in merged.columns:
            continue
        vals = merged[var].dropna().values
        if len(vals) < MIN_ROLLING:
            continue
        current_pctiles[var] = float(np.mean(vals <= val))

    # 5. Build historical percentile vectors — expanding percentile per date
    hist_pctiles = pd.DataFrame(index=merged.index)
    for var in current_pctiles:
        if var in merged.columns and merged[var].notna().sum() > MIN_ROLLING:
            hist_pctiles[var] = merged[var].expanding(min_periods=MIN_ROLLING).rank(pct=True)

    if hist_pctiles.empty:
        return {"status": "insufficient_data", "clones": [], "current_pctiles": current_pctiles}

    # 6. Filter eligible historical dates
    eligible = hist_pctiles.dropna()
    eligible = eligible[eligible.index < cutoff_date]
    eligible = eligible[eligible.index < trade_date_str]
    if eligible.empty or len(eligible) < 10:
        return {"status": "insufficient_data", "clones": [], "current_pctiles": current_pctiles}

    # 7. Weighted Euclidean distance
    available_vars = [v for v in current_pctiles]
    weights_raw = [WEIGHTS[CLONE_VARS.index(v)] for v in available_vars]
    w = np.array(weights_raw) / sum(weights_raw)

    current_arr = np.array([current_pctiles[v] for v in available_vars])
    hist_arr = eligible[available_vars].values.astype(float)
    diffs = hist_arr - current_arr
    distances = np.sqrt(np.sum(w * diffs ** 2, axis=1))

    # 8. Top N closest
    closest_idx = np.argsort(distances)[:top_n]

    # 9. Forward returns
    nifty_series = nifty_df[NIFTY_TICKER].dropna() if NIFTY_TICKER in nifty_df.columns else pd.Series()

    clones = []
    for pos in closest_idx:
        dt = eligible.index[pos].strftime("%Y-%m-%d")
        dist = round(float(distances[pos]), 3)
        fwd = _compute_forward_returns(nifty_series, dt)
        clones.append({
            "date": dt,
            "distance": dist,
            "nifty_30d_fwd": fwd["return_pct"],
            "max_dd": fwd["max_dd"],
        })

    return {
        "status": "ok",
        "clones": clones,
        "current_pctiles": {k: round(float(v), 3) for k, v in current_pctiles.items()},
    }


# ── Tier 1: Global Clone Engine (G3) ─────────────────────────────────

def _fetch_global_history() -> Tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """Fetch history for global clone tickers + SPY/EEM/Nifty forward returns.

    CSV-first for macro + nifty. yfinance only for SPY/EEM (not in CSV).

    Returns:
        (macro_df, spy_series, eem_series, nifty_series)
    """
    # Tier 1: Global macro from CSV
    macro_df = _fetch_csv_history(GLOBAL_TICKERS)
    if macro_df.empty:
        macro_df = _fetch_yfinance(GLOBAL_TICKERS)
    if macro_df.empty:
        return pd.DataFrame(), pd.Series(), pd.Series(), pd.Series()

    # Compute Cu/Au ratio
    if "gold" in macro_df.columns and "copper" in macro_df.columns:
        cu_au = macro_df["copper"] / macro_df["gold"] * 100
        macro_df["cu_au_ratio"] = cu_au

    # Tier 2: Forward return tickers — SPY + EEM from CSV (or yfinance fallback)
    nifty_series = _fetch_nifty_csv_global()
    try:
        fwd_df = _fetch_csv_history({SPY_TICKER: SPY_TICKER, EEM_TICKER: EEM_TICKER})
        if fwd_df.empty:
            fwd_df = _fetch_yfinance({SPY_TICKER: SPY_TICKER, EEM_TICKER: EEM_TICKER})
    except Exception:
        fwd_df = pd.DataFrame()
    spy = fwd_df[SPY_TICKER].dropna() if SPY_TICKER in fwd_df.columns else pd.Series()
    eem = fwd_df[EEM_TICKER].dropna() if EEM_TICKER in fwd_df.columns else pd.Series()

    return macro_df, spy, eem, nifty_series


def _fetch_nifty_csv_global() -> pd.Series:
    """Fetch Nifty series for global clone forward returns from CSV."""
    from src.csv_data import load_history
    df = load_history("nifty")
    if df.empty or "Close" not in df.columns:
        return pd.Series()
    s = df["Close"].dropna()
    s.index = pd.to_datetime(s.index.date)  # tz-naive for matching
    return s.sort_index()


def _compute_cu_au_ratio(current_gold: float, current_copper: float) -> Optional[float]:
    """Compute Cu/Au ratio from current gold and copper prices."""
    if current_gold and current_copper and current_gold > 0:
        return current_copper / current_gold * 100
    return None


def _compute_forward_returns_multi(
    spy_series: pd.Series,
    eem_series: pd.Series,
    nifty_series: pd.Series,
    clone_date: str,
    horizon: int = 30,
) -> Dict[str, Optional[float]]:
    """Compute forward returns for SPY, EEM, and Nifty for a given clone date."""
    result: Dict[str, Optional[float]] = {}
    dt = pd.Timestamp(clone_date)

    for label, series in [("spy_30d_fwd", spy_series), ("eem_30d_fwd", eem_series), ("nifty_30d_fwd", nifty_series)]:
        if series.empty or dt not in series.index:
            result[label] = None
            result[f"{label}_max_dd"] = None
            continue
        entry = series.loc[dt]
        mask = (series.index > dt) & (series.index <= dt + timedelta(days=horizon * 2))
        forward = series[mask].iloc[:horizon]
        if len(forward) < 10:
            result[label] = None
            result[f"{label}_max_dd"] = None
        else:
            result[label] = round((forward.iloc[-1] / entry - 1) * 100, 1)
            result[f"{label}_max_dd"] = round((forward.min() / entry - 1) * 100, 1)

    return result


def find_global_clones(
    current_dxy: float,
    current_us_10y: float,
    current_hyg: float,
    current_gold: float,
    current_copper: float,
    current_usdjpy: float,
    trade_date: Optional[str] = None,
    top_n: int = 3,
    exclude_recent: int = 30,
    min_history: int = 252,
) -> Dict[str, Any]:
    """Find top-N historical global clones via Euclidean distance on 5D percentile vector.

    Tier 1: Global macro regime matching.
    Tier 2: India transmission — Nifty forward return for same clone dates.

    Returns:
        status: "ok" | "insufficient_data"
        clones: list of {date, distance, spy_30d_fwd, eem_30d_fwd, nifty_30d_fwd, max_dd_* }
        current_pctiles: dict of variable→percentile
    """
    trade_date_str = trade_date or datetime.now().strftime("%Y-%m-%d")
    cutoff_dt = pd.Timestamp(trade_date_str) - timedelta(days=exclude_recent)
    cutoff_date = cutoff_dt.strftime("%Y-%m-%d")

    # 1. Fetch history
    macro_df, spy_series, eem_series, nifty_series = _fetch_global_history()
    if macro_df.empty:
        return {"status": "insufficient_data", "clones": [], "current_pctiles": {}}

    # 2. Build merged DataFrame with available global vars
    valid_vars = [v for v in GLOBAL_CLONE_VARS if v in macro_df.columns and macro_df[v].notna().sum() > MIN_ROLLING]
    if len(valid_vars) < 3:
        return {"status": "insufficient_data", "clones": [], "current_pctiles": {}}

    merged = macro_df[valid_vars].dropna(subset=valid_vars, how="all")
    if len(merged) < MIN_ROLLING:
        return {"status": "insufficient_data", "clones": [], "current_pctiles": {}}

    # 3. Current values
    cu_au = _compute_cu_au_ratio(current_gold, current_copper)
    actual: Dict[str, Optional[float]] = {
        "dxy": current_dxy,
        "us_10y": current_us_10y,
        "hyg": current_hyg,
        "cu_au_ratio": cu_au,
        "usdjpy": current_usdjpy,
    }

    # 4. Current percentiles
    current_pctiles: Dict[str, float] = {}
    for var in valid_vars:
        val = actual.get(var)
        if val is None:
            continue
        vals = merged[var].dropna().values
        if len(vals) < MIN_ROLLING:
            continue
        current_pctiles[var] = float(np.mean(vals <= val))

    if not current_pctiles:
        return {"status": "insufficient_data", "clones": [], "current_pctiles": {}}

    # 5. Historical percentiles
    hist_pctiles = pd.DataFrame(index=merged.index)
    for var in current_pctiles:
        if var in merged.columns and merged[var].notna().sum() > MIN_ROLLING:
            hist_pctiles[var] = merged[var].expanding(min_periods=MIN_ROLLING).rank(pct=True)

    if hist_pctiles.empty:
        return {"status": "insufficient_data", "clones": [], "current_pctiles": current_pctiles}

    # 6. Filter eligible dates
    eligible = hist_pctiles.dropna()
    eligible = eligible[eligible.index < cutoff_date]
    eligible = eligible[eligible.index < trade_date_str]
    if eligible.empty or len(eligible) < 10:
        return {"status": "insufficient_data", "clones": [], "current_pctiles": current_pctiles}

    # 7. Weighted Euclidean distance
    available_vars = [v for v in current_pctiles if v in GLOBAL_CLONE_VARS]
    weights_raw = [GLOBAL_WEIGHTS[GLOBAL_CLONE_VARS.index(v)] for v in available_vars]
    w = np.array(weights_raw) / sum(weights_raw)

    current_arr = np.array([current_pctiles[v] for v in available_vars])
    hist_arr = eligible[available_vars].values.astype(float)
    diffs = hist_arr - current_arr
    distances = np.sqrt(np.sum(w * diffs ** 2, axis=1))

    # 8. Top N
    closest_idx = np.argsort(distances)[:top_n]

    # 9. Forward returns for SPY, EEM, Nifty
    clones = []
    for pos in closest_idx:
        dt = eligible.index[pos].strftime("%Y-%m-%d")
        dist = round(float(distances[pos]), 3)
        fwd = _compute_forward_returns_multi(spy_series, eem_series, nifty_series, dt)
        clones.append({
            "date": dt,
            "distance": dist,
            **fwd,
        })

    return {
        "status": "ok",
        "clones": clones,
        "current_pctiles": {k: round(float(v), 3) for k, v in current_pctiles.items()},
    }


def format_global_clone_block(clones_data: Dict[str, Any]) -> str:
    """Format global clone output. Tier 1: Global + Tier 2: India transmission.

    Format:
    🌍 *Global Clones* (Macro State Match)
    1. 2013-08-19 (Taper Tantrum) | Dist: 0.14
       Global: SPX -5.1% | MSCI EM -12.4%
       India: Nifty -8.2% | Max DD: -12.1%
    Median 30D Fwd: SPX -3.4% | MSCI EM -8.1% | Nifty -6.2%
    """
    if clones_data.get("status") != "ok":
        return ""
    clones = clones_data.get("clones", [])
    if not clones:
        return ""

    lines = ["🌍 *Global Clones* (Macro State Match)"]

    spy_fwds = []
    eem_fwds = []
    nifty_fwds = []
    nifty_dds = []

    for i, c in enumerate(clones, 1):
        spy_fwd = c.get("spy_30d_fwd")
        eem_fwd = c.get("eem_30d_fwd")
        nifty_fwd = c.get("nifty_30d_fwd")
        nifty_dd = c.get("nifty_30d_fwd_max_dd")

        spy_str = f"{spy_fwd:+.1f}%" if spy_fwd is not None else "N/A"
        eem_str = f"{eem_fwd:+.1f}%" if eem_fwd is not None else "N/A"
        nifty_str = f"{nifty_fwd:+.1f}%" if nifty_fwd is not None else "N/A"
        dd_str = f"{nifty_dd:.1f}%" if nifty_dd is not None else "N/A"

        lines.append(
            f"{i}. {c['date']} | Dist: {c['distance']:.2f}\n"
            f"   Global: SPX {spy_str} | MSCI EM {eem_str}\n"
            f"   India: Nifty {nifty_str} | Max DD: {dd_str}"
        )
        if spy_fwd is not None:
            spy_fwds.append(spy_fwd)
        if eem_fwd is not None:
            eem_fwds.append(eem_fwd)
        if nifty_fwd is not None:
            nifty_fwds.append(nifty_fwd)
        if nifty_dd is not None:
            nifty_dds.append(nifty_dd)

    if spy_fwds and nifty_fwds:
        med_spy = median(spy_fwds)
        med_eem = median(eem_fwds) if eem_fwds else 0.0
        med_nifty = median(nifty_fwds)
        med_dd = median(nifty_dds) if nifty_dds else 0.0
        lines.append(
            f"*Median 30D Fwd*: SPX {med_spy:+.1f}% | "
            f"MSCI EM {med_eem:+.1f}% | "
            f"Nifty {med_nifty:+.1f}% | "
            f"Max DD {med_dd:.1f}%"
        )

    return "\n".join(lines)


# ── Formatting ────────────────────────────────────────────────────────

def format_clone_block(
    clones_data: Dict[str, Any],
    active_scenarios: Optional[List] = None,
) -> str:
    """Format clone output for Telegram. Strictly deterministic — zero speculation.

    Format:
    🔬 HISTORICAL CLONES (Macro State Match)
    Active Scenario: Geopolitical | Oil Shock
    1. 2013-08-19 | Dist: 0.12
       30D Fwd: -8.2% | Max DD: -12.1%
    Median 30D Fwd: -3.4% | Median Max DD: -6.8%
    """
    if clones_data.get("status") != "ok":
        return ""
    clones = clones_data.get("clones", [])
    if not clones:
        return ""

    lines = ["🔬 *Historical Clones* (Macro State Match)"]

    scenario_labels = []
    if active_scenarios:
        for s in active_scenarios:
            if getattr(s, "severity", None) in ("ACTIVE", "WATCH"):
                scenario_labels.append(s.name.replace("_", " ").title())
    if scenario_labels:
        lines.append(f"Active Scenario: {' | '.join(scenario_labels)}")

    fwd_returns = []
    max_dds = []
    for i, c in enumerate(clones, 1):
        fwd = c.get("nifty_30d_fwd")
        dd = c.get("max_dd")
        fwd_str = f"{fwd:+.1f}%" if fwd is not None else "N/A"
        dd_str = f"{dd:.1f}%" if dd is not None else "N/A"
        lines.append(
            f"{i}. {c['date']} | Dist: {c['distance']:.2f}\n"
            f"   30D Fwd: {fwd_str} | Max DD: {dd_str}"
        )
        if fwd is not None:
            fwd_returns.append(fwd)
        if dd is not None:
            max_dds.append(dd)

    if fwd_returns:
        med_fwd = median(fwd_returns)
        med_dd = median(max_dds) if max_dds else 0.0
        lines.append(
            f"*Median 30D Fwd*: {med_fwd:+.1f}% | "
            f"*Median Max DD*: {med_dd:.1f}%"
        )

    return "\n".join(lines)


# ── Persistence ───────────────────────────────────────────────────────

def save_clones(trade_date: str, clones_data: Dict[str, Any]) -> bool:
    """Save clone results to clone_history table in Supabase."""
    if clones_data.get("status") != "ok":
        return False
    clones = clones_data.get("clones", [])
    if not clones:
        return False

    try:
        client = get_client()
        now = datetime.utcnow().isoformat()
        # Delete existing records for this trade_date, then insert
        client.table("clone_history")\
            .delete()\
            .eq("trade_date", trade_date)\
            .execute()
        for c in clones:
            record = {
                "trade_date": trade_date,
                "clone_date": c["date"],
                "distance": c["distance"],
                "nifty_30d_fwd": c.get("nifty_30d_fwd"),
                "max_dd": c.get("max_dd"),
                "created_at": now,
            }
            client.table("clone_history")\
                .insert(record)\
                .execute()
        return True
    except Exception as e:
        print(f"   ⚠️ Save clones: {e}")
        return False

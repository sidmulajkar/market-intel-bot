"""
MarketState — Central typed schema for all market intelligence modules.

Every module reads/writes typed Pydantic models instead of coupling through
Supabase rows and implicit cron dependencies. New modules should only
interact with MarketState, not raw database queries.

Usage:
    state = MarketState(trade_date="2026-05-26")
    state = fetch_macro(state)        # populates state.macro
    state = compute_flows(state)      # populates state.flows
    ...
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator


def _coerce_str_or_none(v):
    """Coerce value to str if present, else None."""
    if v is None:
        return None
    return str(v)


# ── Macro ────────────────────────────────────────────────────────────────────

class Macro(BaseModel):
    """Core macro indicators — cross-asset anchors and regime labels."""
    vix: Optional[float] = None              # India VIX level
    vix_percentile: Optional[float] = None   # 1Y percentile of VIX
    vix_change_pct: Optional[float] = None   # Day-over-day change
    usdinr: Optional[float] = None           # USD/INR rate
    usdinr_change_pct: Optional[float] = None
    brent: Optional[float] = None            # Brent crude USD/bbl
    brent_change_pct: Optional[float] = None
    gold: Optional[float] = None             # Gold futures
    gold_change_pct: Optional[float] = None
    dxy: Optional[float] = None              # Dollar Index
    dxy_change_pct: Optional[float] = None
    us_10y: Optional[float] = None           # US 10Y Treasury yield
    us_10y_change_pct: Optional[float] = None
    cboe_vix: Optional[float] = None         # CBOE VIX (global fear)
    cboe_vix_change_pct: Optional[float] = None
    hyg: Optional[float] = None              # High yield ETF (credit stress)
    wti: Optional[float] = None              # WTI crude
    copper: Optional[float] = None           # Copper (economic activity)

    # Derived regime labels
    vix_regime: Optional[str] = None         # HIGH/LOW/NORMAL/UNKNOWN
    dxy_signal: Optional[str] = None         # RISING/FALLING/FLAT
    credit_stress: Optional[str] = None      # ELEVATED/NORMAL/LOW


# ── Flows ────────────────────────────────────────────────────────────────────

class Flows(BaseModel):
    """FII/DII cash flows and derivatives positioning."""
    fii_net: Optional[float] = None          # FII net cash (INR cr)
    dii_net: Optional[float] = None          # DII net cash (INR cr)
    absorption_ratio: Optional[float] = None # DII/FII ratio when FII selling
    fii_streak_days: int = 0                 # Consecutive buy/sell days
    dii_streak_days: int = 0
    fii_mood: Optional[str] = None           # AGGRESSIVE_BUY / BUY / NEUTRAL / SELL / AGGRESSIVE_SELL
    dii_mood: Optional[str] = None

    # F&O positioning
    fii_fno_long: Optional[float] = None     # FII F&O long index OI (cr)
    fii_fno_short: Optional[float] = None    # FII F&O short index OI (cr)
    fii_fno_net: Optional[float] = None      # Net F&O
    dii_fno_long: Optional[float] = None
    dii_fno_short: Optional[float] = None
    dii_fno_net: Optional[float] = None


# ── Derivatives ──────────────────────────────────────────────────────────────

class Derivatives(BaseModel):
    """Options chain summary — NIFTY and BANKNIFTY."""
    pcr: Optional[float] = None              # Put-Call Ratio (near-money)
    pcr_signal: Optional[str] = None         # BULLISH / BEARISH / NEUTRAL / CONTRARIAN_BULL / CONTRARIAN_BEAR
    max_pain: Optional[float] = None         # Strike with max OI pain
    spot_price: Optional[float] = None       # Underlying spot price
    gex: Optional[float] = None              # Gamma exposure (net)
    skew_25d: Optional[float] = None         # 25-delta risk reversal
    call_oi_total: Optional[float] = None
    put_oi_total: Optional[float] = None
    iv: Optional[float] = None               # India VIX from options chain
    top_call_strikes: List[float] = Field(default_factory=list)
    top_put_strikes: List[float] = Field(default_factory=list)


# ── Feature Vector ───────────────────────────────────────────────────────────

class FeatureVector(BaseModel):
    """Normalized features (-1 to 1) for ML/forecasting pipelines."""
    momentum_12m: Optional[float] = None     # 12-month Nifty return, normalized
    carry_fii: Optional[float] = None        # FII flow momentum
    sentiment_finbert: Optional[float] = None # Aggregated FinBERT score
    vix_zscore: Optional[float] = None       # VIX deviation from mean
    breadth_score: Optional[float] = None    # A/D ratio normalized
    valuation_zscore: Optional[float] = None # P/E deviation from mean
    pcr_normalized: Optional[float] = None   # PCR normalized to -1..1
    dxy_carry: Optional[float] = None        # DXY impact on EM flows
    skew_signal: Optional[float] = None      # Options skew as fear indicator
    smallcap_ratio: Optional[float] = None   # Nifty Smallcap / Nifty 50 ratio


# ── Forecast ─────────────────────────────────────────────────────────────────

class Forecast(BaseModel):
    """Structured AI forecast — machine-readable, Brier-scoreable."""
    direction: Optional[str] = None          # BULLISH / BEARISH / NEUTRAL
    confidence: Optional[float] = None       # 0-100
    target_horizon: str = "1D"              # 1D / 1W / 1M
    probability_up: Optional[float] = None   # 0.1-0.9 (calibrated, no certainties)
    primary_signals: List[str] = Field(default_factory=list)
    contradiction_warnings: List[str] = Field(default_factory=list)

    # Brier scoring (filled retrospectively by scorecard.py)
    brier_score: Optional[float] = None
    outcome: Optional[str] = None            # HIT / MISS / UNDECIDED
    actual_return: Optional[float] = None


# ── Alert ────────────────────────────────────────────────────────────────────

class Alert(BaseModel):
    """Threshold breach alert."""
    level: str                               # CRITICAL / WARNING / INFO
    signal: str                              # What triggered
    message: str
    value: Optional[float] = None
    threshold: Optional[float] = None


# ── MarketState ──────────────────────────────────────────────────────────────

class MarketState(BaseModel):
    """
    Single source of truth for a trading day.
    All modules receive MarketState as input and return an updated copy.
    """
    trade_date: str                          # YYYY-MM-DD
    macro: Macro = Field(default_factory=Macro)
    flows: Flows = Field(default_factory=Flows)
    derivatives: Derivatives = Field(default_factory=Derivatives)
    features: FeatureVector = Field(default_factory=FeatureVector)
    forecast: Optional[Forecast] = None
    alerts: List[Alert] = Field(default_factory=list)

    # Raw data passthrough (for modules that need original dicts)
    raw: Dict[str, Any] = Field(default_factory=dict)

    # Computed narratives (injected into AI prompt)
    narratives: Dict[str, str] = Field(default_factory=dict)

    # Regime / phase labels
    bull_bear_score: Optional[float] = None  # -40 to +40
    bull_bear_normalized: Optional[float] = None  # 0-100
    bull_bear_confidence: Optional[float] = None
    market_phase: Optional[str] = None       # ACCUMULATION / DISTRIBUT / MARKUP / DECLINE
    cross_asset_regime: Optional[str] = None # RISK_ON / RISK_OFF / STAGFLATION
    dominant_factor: Optional[str] = None    # Top contributing factor

    # Regime arbiter output (single source of truth — all formatters read this)
    final_regime: Optional[str] = None       # BULLISH/BEARISH/NEUTRAL/DEFENSIVE
    final_regime_confidence: Optional[str] = None  # HIGH/MEDIUM/LOW
    final_dominant_driver: Optional[str] = None    # e.g., "USDINR ₹95.7 + Brent $93"
    final_override_reason: Optional[str] = None    # "" or "macro_extreme"

    # Validation / quality
    data_quality: str = "real"               # real / estimated / degraded
    missing_sources: List[str] = Field(default_factory=list)
    compute_budget_pct: Optional[float] = None

    # Headline dedup — MD5 hashes of rendered headlines across jobs
    seen_headlines: List[str] = Field(default_factory=list)

    @field_validator('cross_asset_regime', mode='before')
    @classmethod
    def coerce_cross_asset_regime(cls, v):
        """Coerce int → str for cross_asset_regime (upstream sometimes writes confirmation_pct int)."""
        return _coerce_str_or_none(v)

    def with_macro(self, data: Dict) -> "MarketState":
        """Convenience: update macro fields from dict."""
        for key, val in data.items():
            if hasattr(self.macro, key):
                setattr(self.macro, key, val)
        return self

    def with_flows(self, data: Dict) -> "MarketState":
        """Convenience: update flows fields from dict."""
        for key, val in data.items():
            if hasattr(self.flows, key):
                setattr(self.flows, key, val)
        return self

    def with_derivatives(self, data: Dict) -> "MarketState":
        """Convenience: update derivatives fields from dict."""
        for key, val in data.items():
            if hasattr(self.derivatives, key):
                setattr(self.derivatives, key, val)
        return self

    def with_features(self, data: Dict) -> "MarketState":
        """Convenience: update feature vector from dict."""
        for key, val in data.items():
            if hasattr(self.features, key):
                setattr(self.features, key, val)
        return self

    def add_alert(self, level: str, signal: str, message: str, value: Optional[float] = None, threshold: Optional[float] = None):
        self.alerts.append(Alert(level=level, signal=signal, message=message, value=value, threshold=threshold))

    def add_narrative(self, key: str, text: str):
        self.narratives[key] = text

    def has_data(self, field_name: str) -> bool:
        """Check if a top-level sub-model has any non-None data."""
        obj = getattr(self, field_name, None)
        if obj is None:
            return False
        if isinstance(obj, BaseModel):
            return any(v is not None for k, v in obj.model_dump().items() if k not in ("streak_days",))
        return bool(obj)

    def summary(self) -> str:
        """One-line summary for logging."""
        parts = [f"Date={self.trade_date}"]
        if self.macro.vix is not None:
            parts.append(f"VIX={self.macro.vix}")
        if self.macro.usdinr is not None:
            parts.append(f"USDINR={self.macro.usdinr}")
        if self.macro.brent is not None:
            parts.append(f"BRENT={self.macro.brent}")
        if self.flows.fii_net is not None:
            parts.append(f"FII={self.flows.fii_net:+.0f}cr")
        if self.derivatives.pcr is not None:
            parts.append(f"PCR={self.derivatives.pcr:.2f}")
        if self.bull_bear_score is not None:
            parts.append(f"BB={self.bull_bear_score:+.1f}")
        if self.market_phase:
            parts.append(f"Phase={self.market_phase}")
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for Supabase JSONB storage."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketState":
        """Reconstruct from dict (Supabase JSONB retrieval)."""
        return cls.model_validate(data)

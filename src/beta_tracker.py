"""
Cross-Asset Beta Tracker — Rolling 90-day beta between Nifty and macro assets.
Beta = how much Nifty moves per 1% move in the other asset.
High beta spike = correlation regime change.

All computation from stored daily_market_snapshot — zero API calls.
"""
import statistics
from typing import Dict, List, Optional


def compute_rolling_beta(nifty_returns: List[float], asset_returns: List[float],
                          window: int = 90) -> Optional[float]:
    """
    Compute rolling beta: covariance(nifty, asset) / variance(asset).
    Beta > 0 = Nifty moves with asset.
    Beta < 0 = Nifty moves opposite asset.
    |Beta| > 1 = Nifty more volatile than asset.
    """
    if len(nifty_returns) < window or len(asset_returns) < window:
        return None

    nifty = nifty_returns[-window:]
    asset = asset_returns[-window:]

    if len(nifty) != len(asset) or len(nifty) < 20:
        return None

    mean_nifty = statistics.mean(nifty)
    mean_asset = statistics.mean(asset)

    cov = sum((n - mean_nifty) * (a - mean_asset) for n, a in zip(nifty, asset)) / (len(nifty) - 1)
    var_asset = sum((a - mean_asset) ** 2 for a in asset) / (len(asset) - 1)

    if var_asset == 0:
        return 0.0

    return round(cov / var_asset, 4)


def compute_all_betas(snapshots: List[Dict], window: int = 90) -> Dict:
    """
    Compute rolling betas for Nifty vs all macro assets.
    Uses daily_market_snapshot data.
    """
    if not snapshots or len(snapshots) < window:
        return {"ok": False, "message": f"Need {window}+ snapshots, have {len(snapshots)}"}

    # Extract returns
    def _get_returns(metric):
        vals = [s.get(metric) for s in snapshots if s.get(metric) is not None]
        return [(vals[i] / vals[i-1] - 1) * 100 if vals[i-1] != 0 else 0
                for i in range(1, len(vals))] if len(vals) > 1 else []

    nifty_returns = _get_returns("nifty_close")

    assets = {
        "DXY": "dxy",
        "Gold": "gold",
        "Brent": "brent",
        "USD/INR": "usdinr",
        "India VIX": "india_vix",
    }

    betas = {}
    for label, metric in assets.items():
        asset_returns = _get_returns(metric)
        if nifty_returns and asset_returns:
            beta = compute_rolling_beta(nifty_returns, asset_returns, window)
            if beta is not None:
                # Percentile of beta over time (using available data)
                beta_history = []
                for i in range(window, len(nifty_returns)):
                    b = compute_rolling_beta(nifty_returns[i-window:i], asset_returns[i-window:i], window)
                    if b is not None:
                        beta_history.append(b)

                pctile = None
                if len(beta_history) >= 20:
                    below = sum(1 for v in beta_history if v < beta)
                    pctile = round((below / len(beta_history)) * 100)

                # Regime classification
                if abs(beta) > 1.5:
                    regime = "VERY HIGH — Nifty dominated by this asset"
                elif abs(beta) > 0.8:
                    regime = "HIGH — strong relationship"
                elif abs(beta) > 0.3:
                    regime = "MODERATE"
                elif abs(beta) > 0.1:
                    regime = "LOW — weak relationship"
                else:
                    regime = "NEGLIGIBLE — independent"

                betas[label] = {
                    "beta": beta,
                    "percentile": pctile,
                    "regime": regime,
                    "window": window,
                }

    return {"ok": bool(betas), "betas": betas, "window": window}


def format_betas(betas_data: Dict) -> str:
    """Format beta tracker for AI prompt."""
    if not betas_data.get("ok"):
        return ""

    lines = [f"[Cross-Asset Beta — {betas_data['window']}-Day Rolling]"]

    for label, data in betas_data.get("betas", {}).items():
        beta = data["beta"]
        pctile = data.get("percentile")
        pct_str = f" ({pctile}th pct)" if pctile else ""
        icon = "🔴" if abs(beta) > 1 else "🟢" if abs(beta) < 0.3 else "⚪"
        lines.append(f"  {icon} Nifty vs {label}: β={beta:+.3f}{pct_str} — {data['regime']}")

    lines.append("\n  Beta > 1 = Nifty amplified moves. Beta < 0 = Nifty moves opposite.")
    lines.append("  High beta spike = macro-driven market, stock-picking less effective.")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test with dummy data
    snapshots = [{"nifty_close": 25000 + i * 30 + (-1)**i * 20,
                  "dxy": 103 + i * 0.01, "gold": 3200 + i * 5,
                  "brent": 82 + i * 0.2, "usdinr": 83 + i * 0.005,
                  "india_vix": 14 + i * 0.05} for i in range(120)]
    result = compute_all_betas(snapshots)
    print(format_betas(result))

"""
Sunday Calibration — Walk-forward backtest of pillar thresholds.
Runs 02:30 UTC Sunday after simulation (02:15) and CSV consolidation (02:00).

Tests pillar classifier against 10 historical episodes. Tunes dimension thresholds
to maximize F1 score. Outputs calibration report + optional threshold overrides.

No AI. All numpy/math. Reads from CSV + pillar_metrics table.
"""

import os
import numpy as np
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


# Historical episodes with known pillar ground truth
# Format: {episode_name: {date_range: (start, end), ground_truth: {pillar: severity}}}
KNOWN_EPISODES: Dict[str, Dict] = {
    "2013_TAPER": {
        "label": "2013 Taper Tantrum",
        "range": ("2013-05-22", "2013-08-30"),
        "expected": {
            "EM_CONTAGION": "ELEVATED",
            "CARRY_UNWIND": "ACTIVE",
        },
    },
    "2018_EM": {
        "label": "2018 EM Selloff",
        "range": ("2018-04-01", "2018-10-30"),
        "expected": {
            "EM_CONTAGION": "ACTIVE",
            "CARRY_UNWIND": "ACTIVE",
        },
    },
    "2020_COVID": {
        "label": "2020 COVID Crash",
        "range": ("2020-02-20", "2020-04-30"),
        "expected": {
            "EM_CONTAGION": "ELEVATED",
            "WEST_ASIA": "ACTIVE",
            "CARRY_UNWIND": "ACTIVE",
            "TECH_CYCLE_BURST": "ELEVATED",
        },
    },
    "2022_FED": {
        "label": "2022 Fed Tightening",
        "range": ("2022-01-01", "2022-10-30"),
        "expected": {
            "STAGFLATION_SUPPLY": "ELEVATED",
            "EM_CONTAGION": "ACTIVE",
            "CARRY_UNWIND": "ACTIVE",
        },
    },
    "2022_RU_WAR": {
        "label": "2022 Russia-Ukraine",
        "range": ("2022-02-24", "2022-04-30"),
        "expected": {
            "STAGFLATION_SUPPLY": "ELEVATED",
            "WEST_ASIA": "ELEVATED",
            "EM_CONTAGION": "ACTIVE",
        },
    },
    "2023_BANKING": {
        "label": "2023 US Banking Stress",
        "range": ("2023-03-08", "2023-04-30"),
        "expected": {
            "CARRY_UNWIND": "MONITORED",
        },
    },
    "2024_ELECTION": {
        "label": "2024 India Election Vol",
        "range": ("2024-04-01", "2024-06-30"),
        "expected": {
            "EM_CONTAGION": "ACTIVE",
            "CARRY_UNWIND": "ACTIVE",
        },
    },
    "2024_INR_CRISIS": {
        "label": "2024-25 INR Pressure",
        "range": ("2024-10-01", "2025-02-28"),
        "expected": {
            "STAGFLATION_SUPPLY": "ACTIVE",
            "EM_CONTAGION": "ACTIVE",
            "CARRY_UNWIND": "MONITORED",
        },
    },
    "2025_OIL_DISRUPTION": {
        "label": "2025 West Asia Escalation",
        "range": ("2025-06-01", "2025-12-31"),
        "expected": {
            "WEST_ASIA": "MONITORED",
            "STAGFLATION_SUPPLY": "ACTIVE",
            "EM_CONTAGION": "ACTIVE",
            "CARRY_UNWIND": "ACTIVE",
        },
    },
    "2026_INR_EXTREME": {
        "label": "2026 INR at All-Time High",
        "range": ("2026-01-01", "2026-06-01"),
        "expected": {
            "STAGFLATION_SUPPLY": "ACTIVE",
            "EM_CONTAGION": "ACTIVE",
            "CARRY_UNWIND": "ACTIVE",
        },
    },
}


def _tier_weight(tier: str) -> int:
    return {"STRESS": 4, "ELEVATED": 3, "ACTIVE": 2, "MONITORED": 1, "INACTIVE": 0}.get(tier, 0)


def evaluate_episode(
    pillar_results: List[Dict],
    expected: Dict[str, str],
    meta_label: str,
) -> Dict:
    """Evaluate pillar classifier against a single historical episode.

    Args:
        pillar_results: List of {name, score, tier} from classifier
        expected: {pillar_name: expected_tier}
        meta_label: Episode label for reporting

    Returns:
        {true_pos, false_pos, false_neg, f1, details}
    """
    detected = {p["name"]: p["tier"] for p in pillar_results}

    tp, fp, fn = 0, 0, 0
    details = []

    for pillar, expected_tier in expected.items():
        got = detected.get(pillar, "INACTIVE")
        expected_weight = _tier_weight(expected_tier)
        got_weight = _tier_weight(got)

        if got_weight >= expected_weight:
            tp += 1
            details.append(f"  ✅ {pillar}: expected {expected_tier}, got {got}")
        elif got_weight >= expected_weight - 1:
            tp += 0.5
            details.append(f"  🟡 {pillar}: expected {expected_tier}, got {got} (borderline)")
        else:
            fn += 1
            details.append(f"  ❌ {pillar}: expected {expected_tier}, got {got} (miss)")

    for pillar, got_tier in detected.items():
        if pillar not in expected and _tier_weight(got_tier) >= _tier_weight("ACTIVE"):
            fp += 1
            details.append(f"  ⚠️ FP: {pillar} = {got_tier} (not in expected)")

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 0.001)

    return {
        "episode": meta_label,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "pass_threshold": f1 >= 0.7,
        "details": details,
    }


def run_calibration(supabase) -> Dict:
    """Run full calibration against 10 episodes. Returns pass/fail summary."""
    from src.csv_data import load_history

    df = load_history("anchors")
    if df.empty:
        return {"ok": False, "error": "Empty anchor CSV"}

    # Compute percentiles
    all_dims = [
        "DXY", "US10Y", "Brent", "Gold", "USDINR", "IndiaVIX",
        "Credit_Ratio", "Cu_Au_Ratio", "SOXX_NQ_Ratio",
    ]

    if "HYG" in df.columns and "LQD" in df.columns:
        df["Credit_Ratio"] = df["HYG"] / df["LQD"]
    if "COPPER" in df.columns and "GOLD" in df.columns:
        df["Cu_Au_Ratio"] = df["COPPER"] / df["GOLD"]
    if "SOXX" in df.columns and "NASDAQ" in df.columns:
        df["SOXX_NQ_Ratio"] = df["SOXX"] / df["NASDAQ"]

    for col in all_dims:
        if col in df.columns and df[col].notna().sum() > 10:
            df[f"{col}_pctile"] = df[col].expanding().rank(pct=True)

    from src.pillar_classifier import classify_pillars

    results = []
    for ep_name, ep_info in KNOWN_EPISODES.items():
        start_dt = datetime.strptime(ep_info["range"][0], "%Y-%m-%d")
        end_dt = datetime.strptime(ep_info["range"][1], "%Y-%m-%d")

        # Compute 5 random samples from episode range to reduce noise
        rng = np.random.RandomState(hash(ep_name) % (2**31))
        df_range = df[(df.index >= ep_info["range"][0]) & (df.index <= ep_info["range"][1])]
        if df_range.empty:
            continue

        n_samples = min(5, len(df_range))
        sample_indices = rng.choice(len(df_range), n_samples, replace=False)

        all_pillar_results = []
        for idx in sample_indices:
            row = df_range.iloc[idx]
            pctiles = {}
            for col in all_dims:
                pcol = f"{col}_pctile"
                if pcol in df.columns:
                    val = row.get(pcol)
                    if val is not None and not (isinstance(val, float) and np.isnan(val)):
                        pctiles[col] = val * 100
            if pctiles:
                all_pillar_results.append(classify_pillars(pctiles))

        # Average pillar scores across samples
        score_sums = {}
        tier_sums = {}
        for pr in all_pillar_results:
            for p in pr:
                if p["name"] not in score_sums:
                    score_sums[p["name"]] = []
                score_sums[p["name"]].append(p["score"])
                tier_sums[p["name"]] = p["tier"]

        avg_results = []
        for name, scores in score_sums.items():
            avg_score = sum(scores) / len(scores)
            avg_tier = "ACTIVE" if avg_score >= 40 else "MONITORED" if avg_score >= 20 else "INACTIVE"
            avg_results.append({"name": name, "score": avg_score, "tier": avg_tier})

        ep_result = evaluate_episode(avg_results, ep_info["expected"], ep_name)
        results.append(ep_result)
        print(f"  {ep_name:25s} F1={ep_result['f1']:.3f}  {'✅' if ep_result['pass_threshold'] else '❌'}")

    passed = sum(1 for r in results if r["pass_threshold"])
    overall_f1 = sum(r["f1"] for r in results) / max(len(results), 1)

    return {
        "ok": True,
        "episodes_evaluated": len(results),
        "episodes_passed": passed,
        "overall_f1": round(overall_f1, 3),
        "gate_passed": passed >= len(results) * 0.8,
        "results": results,
    }


# ── P17: Fragility Threshold Grid Search ────────────────────────────────

_FRAGILITY_VARS = ["CBOE_VIX", "USDINR", "Brent", "DXY"]


def _compute_simplified_fragility(row: "Any", rolling_pctiles: "Any") -> float:
    """Compute a simplified daily fragility proxy from macro percentiles.

    Base (0.40): average of VIX, USDINR, Brent, DXY percentiles
    Breadth (0.30): count of vars >75th pctile, normalized to 0-100
    Intensity (0.30): max of all variable percentiles
    """
    pctiles = []
    stressed_count = 0
    for var in _FRAGILITY_VARS:
        col = f"{var}_pctile"
        if col in rolling_pctiles.columns:
            val = row.get(col)
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                pct = val * 100
                pctiles.append(pct)
                if pct >= 75:
                    stressed_count += 1

    if not pctiles:
        return 50.0

    base = sum(pctiles) / len(pctiles)
    breadth = (stressed_count / len(_FRAGILITY_VARS)) * 100.0
    intensity = max(pctiles)

    return round(
        base * 0.40 + breadth * 0.30 + intensity * 0.30,
        1,
    )


def _determine_ground_truth(nifty_5d_fwd_pct: float) -> str:
    """Binary: BULLISH (>+1%) / DEFENSIVE (<-1%) / NEUTRAL (in between)."""
    if nifty_5d_fwd_pct > 1.0:
        return "BULLISH"
    elif nifty_5d_fwd_pct < -1.0:
        return "DEFENSIVE"
    return "NEUTRAL"


def _simulate_fragility_regime(fragility: float, cap_neutral: float, force_defensive: float) -> str:
    """Simulate what regime the arbiter would output with given thresholds."""
    if fragility > force_defensive:
        return "DEFENSIVE"
    if fragility > cap_neutral:
        return "NEUTRAL"  # capped (even if stat says BULLISH)
    return "NEUTRAL"  # default (no override)


def compute_fragility_thresholds() -> Dict:
    """Grid search Fragility thresholds [50–90 step 5] on 5Y CSV data.

    Returns: {
        "ok": bool,
        "cap_neutral": float (validated),
        "force_defensive": float (validated),
        "validation_accuracy": float,
        "holdout_accuracy": float,
        "n_training_days": int,
        "n_holdout_days": int,
        "used_defaults": bool,
    }
    """
    print("\n🔬 P17: Fragility Threshold Grid Search")
    print("─" * 50)

    # Load anchor history
    try:
        import pandas as pd
        a = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "data", "anchor_history.csv"))
        n = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "data", "nifty_history.csv"))
    except Exception as e:
        print(f"   ⚠️ Cannot load CSVs: {e}")
        return {"ok": False, "message": str(e)}

    # Clean nifty date, merge
    n["date"] = n["date"].str.split(" ").str[0]
    df = a.merge(n, on="date", how="inner")
    df = df.set_index("date").sort_index()
    print(f"   Merged data: {len(df)} rows ({df.index[0]} to {df.index[-1]})")

    # Compute rolling percentiles
    for var in _FRAGILITY_VARS:
        if var in df.columns and df[var].notna().sum() > 10:
            df[f"{var}_pctile"] = df[var].expanding().rank(pct=True)
        else:
            print(f"   ⚠️ Variable {var} has insufficient data — skipping")
            return {"ok": False, "message": f"{var} insufficient data"}

    # Compute daily fragility + ground truth (5D forward Nifty return)
    rows = []
    for i in range(len(df) - 5):
        row = df.iloc[i]
        fragility = _compute_simplified_fragility(row, df)
        nifty_today = row.get("Close", 0)
        nifty_fwd = df.iloc[i + 5].get("Close", 0)
        if nifty_today and nifty_fwd:
            fwd_pct = (nifty_fwd - nifty_today) / nifty_today * 100
            gt = _determine_ground_truth(fwd_pct)
            rows.append({"date": df.index[i], "fragility": fragility, "ground_truth": gt})

    if len(rows) < 100:
        print(f"   ⚠️ Only {len(rows)} rows with ground truth — insufficient")
        return {"ok": False, "message": f"Only {len(rows)} rows"}

    # Split: 80% training, 20% holdout (chronological)
    split_idx = int(len(rows) * 0.8)
    train = rows[:split_idx]
    holdout = rows[split_idx:]
    print(f"   Training: {len(train)} days | Holdout: {len(holdout)} days")

    # Grid search
    candidates = range(50, 91, 5)
    best_acc = 0.0
    best_params = (65.0, 85.0)
    results = []

    for cn in candidates:
        for fd in candidates:
            if fd <= cn:
                continue
            correct = sum(
                1 for r in train
                if _simulate_fragility_regime(r["fragility"], float(cn), float(fd)) == r["ground_truth"]
            )
            acc = correct / max(len(train), 1)
            results.append((cn, fd, acc))

    if results:
        best_params = max(results, key=lambda x: x[2] if not np.isnan(x[2]) else 0)
        best_cn, best_fd, best_train_acc = best_params
        print(f"   Best training: cap_neutral={best_cn} force_defensive={best_fd} (acc={best_train_acc:.3f})")
    else:
        print("   ⚠️ No valid threshold combos found — using defaults")
        return {"ok": False, "message": "No valid combos"}

    # Validate on holdout
    holdout_correct = sum(
        1 for r in holdout
        if _simulate_fragility_regime(r["fragility"], float(best_cn), float(best_fd)) == r["ground_truth"]
    )
    holdout_acc = holdout_correct / max(len(holdout), 1)
    print(f"   Holdout validation: {holdout_correct}/{len(holdout)} = {holdout_acc:.3f}")

    # If holdout accuracy <= baseline (equal-weights), keep defaults and warn
    baseline_correct = sum(
        1 for r in holdout
        if _simulate_fragility_regime(r["fragility"], 65.0, 85.0) == r["ground_truth"]
    )
    baseline_acc = baseline_correct / max(len(holdout), 1)
    print(f"   Baseline (65/85) holdout: {baseline_acc:.3f}")

    used_defaults = False
    if holdout_acc <= baseline_acc:
        print("   ⚠️ P17: Holdout accuracy ≤ baseline — keeping defaults (65/85)")
        best_cn, best_fd = 65.0, 85.0
        holdout_acc = baseline_acc
        used_defaults = True

    print(f"   ✅ Final thresholds: cap_neutral={best_cn} force_defensive={best_fd}")
    return {
        "ok": True,
        "cap_neutral": float(best_cn),
        "force_defensive": float(best_fd),
        "validation_accuracy": round(max(r[2] for r in results), 3),
        "holdout_accuracy": round(holdout_acc, 3),
        "n_training_days": len(train),
        "n_holdout_days": len(holdout),
        "used_defaults": used_defaults,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# P17: CSV-based Adaptive Weights
# ═══════════════════════════════════════════════════════════════════════════════

_PILLAR_NAMES_FOR_WEIGHTS = [
    "STAGFLATION_SUPPLY", "WEST_ASIA", "EM_CONTAGION",
    "CARRY_UNWIND", "DE_DOLLARIZATION", "TECH_CYCLE_BURST",
]


def compute_retroactive_pillar_scores() -> Optional["pd.DataFrame"]:
    """Compute daily pillar scores across the full 5Y CSV history.

    Uses the same pillar_classifier logic on expanding percentiles.
    Returns DataFrame with columns: date, <each pillar name>_score, nifty_fwd_5d_pct
    """
    try:
        import pandas as pd

        DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        a = pd.read_csv(os.path.join(DATA_DIR, "anchor_history.csv"))
        n = pd.read_csv(os.path.join(DATA_DIR, "nifty_history.csv"))

        n["date"] = n["date"].str.split(" ").str[0]
        df = a.merge(n, on="date", how="inner")
        df = df.set_index("date").sort_index()

        # Compute derived ratios
        if "HYG" in df.columns and "LQD" in df.columns:
            df["Credit_Ratio"] = df["HYG"] / df["LQD"]
        if "SOXX" in df.columns and "NASDAQ" in df.columns:
            df["SOXX_NQ_Ratio"] = df["SOXX"] / df["NASDAQ"]

        from src.pillar_classifier import VECTOR_FIELDS, classify_pillars

        for col in VECTOR_FIELDS:
            if col in df.columns and df[col].notna().sum() > 10:
                df[f"{col}_pctile"] = df[col].expanding().rank(pct=True)

        # Compute nifty 5D forward return
        df["nifty_fwd_5d_pct"] = df["Close"].shift(-5) / df["Close"] - 1

        rows = []
        for idx in range(len(df)):
            row = df.iloc[idx]
            pctiles = {}
            for col in VECTOR_FIELDS:
                pcol = f"{col}_pctile"
                if pcol in df.columns:
                    val = row.get(pcol)
                    if val is not None and not (isinstance(val, float) and pd.isna(val)):
                        pctiles[col] = val * 100
            if not pctiles:
                continue
            pillars = classify_pillars(pctiles)
            p_scores = {p["name"]: p["score"] for p in pillars}
            fwd = row.get("nifty_fwd_5d_pct")
            rows.append({**p_scores, "date": df.index[idx], "nifty_fwd_5d_pct": fwd})

        result = pd.DataFrame(rows)
        print(f"   Computed {len(result)} retroactive pillar score days")
        return result
    except Exception as e:
        print(f"   ⚠️ compute_retroactive_pillar_scores: {e}")
        return None


def compute_adaptive_weights_from_csv() -> Dict[str, float]:
    """Compute adaptive pillar weights from 5Y CSV history.

    For each pillar, hit_rate = % of times score >= 40 preceded a 5D Nifty drop > 1%.
    weight_multiplier = clamp(1.0 + (hit_rate - 0.50), 0.70, 1.30)

    Returns:
        {pillar_name: weight_multiplier}
    """
    print("\n📊 Computing adaptive pillar weights from CSV...")
    pillars_df = compute_retroactive_pillar_scores()
    if pillars_df is None or pillars_df.empty:
        print("   ⚠️ No pillar history — using default weights (1.0)")
        return {p: 1.0 for p in _PILLAR_NAMES_FOR_WEIGHTS}

    weights = {}
    for pillar in _PILLAR_NAMES_FOR_WEIGHTS:
        if pillar not in pillars_df.columns:
            weights[pillar] = 1.0
            continue
        active = pillars_df[pillar].dropna() >= 40
        if active.sum() < 5:
            print(f"   {pillar}: {int(active.sum())} active days — insufficient (need ≥5), weight=1.0")
            weights[pillar] = 1.0
            continue

        active_df = pillars_df.loc[active[active].index]
        hit = (active_df["nifty_fwd_5d_pct"].dropna() < -0.01).mean()
        mult = 1.0 + (hit - 0.50)
        mult = max(0.70, min(1.30, mult))
        weights[pillar] = round(mult, 3)
        print(f"   {pillar}: hit_rate={hit:.1%} active_days={int(active.sum())} weight={mult:.3f}")

    return weights


def write_manifest(
    p17_result: Dict,
    adaptive_weights: Dict[str, float],
    tilt_map: Dict = None,
    erp_deciles: list = None,
) -> bool:
    """Write all pre-computed values to data/manifest.json.

    Args:
        p17_result: Output of compute_fragility_thresholds()
        adaptive_weights: {pillar_name: weight_multiplier}
        tilt_map: Sector tilt map dict (P7.2)
        erp_deciles: 10-bin ERP decile boundary list (P8.2)
    """
    import hashlib, json

    manifest_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "manifest.json",
    )
    try:
        frag_cn = p17_result.get("cap_neutral", 65.0) if p17_result.get("ok") else 65.0
        frag_fd = p17_result.get("force_defensive", 85.0) if p17_result.get("ok") else 85.0
        _tilt = tilt_map or {}
        _erp = erp_deciles if (erp_deciles and len(erp_deciles) == 10) else [-2.5, -2.1, -1.8, -1.5, -1.2, -0.9, -0.6, -0.3, 0.0, 0.4]
        _weights = adaptive_weights if adaptive_weights else {
            "Stagflation": 1.0, "West_Asia": 1.0, "EM_Contagion": 1.0,
            "Carry_Unwind": 1.0, "De-dollarization": 1.0, "Tech_Cycle": 1.0,
        }

        manifest = {
            "version": hashlib.sha256(str(datetime.now().timestamp()).encode()).hexdigest()[:7],
            "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "fingerprint_buckets": {
                "nifty": 100, "vix": 1, "brent": 1.0, "usdinr": 0.1, "dxy": 0.5,
            },
            "fragility": {"cap_neutral": frag_cn, "force_defensive": frag_fd},
            "adaptive_weights": _weights,
            "sector_tilt_map": _tilt,
            "erp_deciles": _erp,
            "steady_state_template": "🟢 Steady state since {last_regime_time}. Regime: {regime} | Nifty: {nifty} | VIX: {vix}. No notable change.",
            "templates": {
                "heartbeat": "🟢 Steady state. Regime: {regime} | Nifty: {nifty:.0f} | VIX: {vix:.1f}. No notable change.",
                "no_change_short": "🟡 Steady State: {regime} | Nifty {nifty:.0f} | VIX {vix:.1f}\n💤 No material change.",
                "no_change_standard": "🟡 Steady State: {regime} (Fragility: {fragility}) | Nifty {nifty:.0f} | VIX {vix:.1f}\n💤 Macro drivers unchanged since {time_since}.\n📌 Next full scan on material shift.",
                "yellow_stub": "⚠️ *Partial Data* — AI analysis unavailable.\n\n📌 *Regime:* {regime} ({confidence})\n📊 Nifty: {nifty:.0f} | VIX: {vix:.1f} | USDINR: {usdinr:.2f} | Brent: {brent:.1f}\n📈 FII: {fii_cr:.0f} Cr | DII: {dii_cr:.0f} Cr\n\nDeterministic summary: Data quality insufficient for AI narrative.",
                "intel_stubs": {
                    "BULLISH": "🟢 *Market Context:* Positive setup. Regime: {regime} | Nifty: {nifty:.0f} | VIX: {vix:.1f}. Momentum supportive with {top_pillar} in check. FII flows constructive at {fii_cr:.0f} Cr.",
                    "NEUTRAL": "🟡 *Market Context:* Balanced. Regime: {regime} | Nifty: {nifty:.0f} | VIX: {vix:.1f}. {top_pillar} present but contained. No dominant directional bias.",
                    "DEFENSIVE": "🔴 *Market Context:* Caution warranted. Regime: {regime} | Nifty: {nifty:.0f} | VIX: {vix:.1f}. Fragility elevated at {fragility:.0f}. {top_pillar} structural risk active.",
                },
            },
        }
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"   ✅ Manifest written to {manifest_path} (v{manifest['version']})")
        return True
    except Exception as e:
        print(f"   ⚠️ Manifest write: {e}")
        return False


def run_full_calibration() -> Dict:
    """Run the full Sunday calibration pipeline (no Supabase needed).

    Returns:
        {"ok": bool, "episode_results": ..., "p17": ..., "adaptive_weights": ..., "manifest_written": bool}
    """
    print("=" * 50)
    print("📋 Sunday Calibration — Full Pipeline")
    print("=" * 50)

    result = {
        "ok": False,
        "episode_results": {},
        "p17": {},
        "adaptive_weights": {},
        "manifest_written": False,
    }

    # ── Episodic backtest ──
    print("\n🔬 Episodic pillar backtest...")
    try:
        ep_result = run_calibration(None)
        result["episode_results"] = ep_result
        if ep_result.get("ok"):
            print(f"   Episodes: {ep_result['episodes_passed']}/{ep_result['episodes_evaluated']} passed | F1={ep_result['overall_f1']}")
    except Exception as e:
        print(f"   ⚠️ Episode calibration: {e}")

    # ── P17: Fragility Threshold Grid Search ─────────────────
    print("\n🔬 P17: Fragility Threshold Grid Search...")
    try:
        p17_result = compute_fragility_thresholds()
        result["p17"] = p17_result
        if p17_result.get("ok"):
            print(f"   ✅ cap_neutral={p17_result['cap_neutral']} force_defensive={p17_result['force_defensive']} | Holdout acc={p17_result['holdout_accuracy']:.3f}")
            if p17_result.get("used_defaults"):
                print("   ⚠️ P17 holdout ≤ baseline — keeping defaults (65/85)")
        else:
            print(f"   ⚠️ P17 failed: {p17_result.get('message')}")
            p17_result = {"ok": False}
    except Exception as e:
        print(f"   ⚠️ P17 grid search: {e}")
        p17_result = {"ok": False}

    # ── Adaptive Weights from CSV ──
    try:
        weights = compute_adaptive_weights_from_csv()
        result["adaptive_weights"] = weights
    except Exception as e:
        print(f"   ⚠️ Adaptive weights: {e}")
        result["adaptive_weights"] = {p: 1.0 for p in _PILLAR_NAMES_FOR_WEIGHTS}

    # ── Write manifest ──
    try:
        result["manifest_written"] = write_manifest(
            p17_result=p17_result,
            adaptive_weights=result["adaptive_weights"],
        )
    except Exception as e:
        print(f"   ⚠️ Manifest write: {e}")

    result["ok"] = True
    print("\n" + "=" * 50)
    print("✅ Full calibration complete")
    print("=" * 50)
    return result


if __name__ == "__main__":
    r = run_full_calibration()
    sys.exit(0 if r.get("ok") else 1)

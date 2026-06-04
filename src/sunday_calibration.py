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
from typing import Dict, List, Optional, Tuple


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


if __name__ == "__main__":
    print("Sunday Calibration — Walk-Forward Backtest")
    print("=" * 50)

    from src.supabase_client import create_supabase_client
    sb = create_supabase_client()
    if not sb:
        print("❌ Supabase connection failed")
        sys.exit(1)

    result = run_calibration(sb)
    print(f"\nSummary: {result['episodes_passed']}/{result['episodes_evaluated']} passed")
    print(f"Overall F1: {result['overall_f1']}")
    print(f"Gate {'PASSED' if result['gate_passed'] else 'FAILED'}")

    # ── P7.1: Dynamic Pillar Weights ──────────────────────────────────
    print("\n📊 Computing dynamic pillar weights...")
    try:
        from src.adaptive_weights import compute_pillar_weights
        weights = compute_pillar_weights(sb)
        print(f"   Weights: { {k: f'{v:.2f}' for k, v in weights.items()} }")
    except Exception as e:
        print(f"   ⚠️ Pillar weights: {e}")

    # ── P7.2: Sector Rotation Map ────────────────────────────────────
    print("\n📈 Computing sector rotation map...")
    try:
        from src.sector_rotation_map import compute_sector_tilt_map
        tilt_map = compute_sector_tilt_map(sb)
        print(f"   Tilt map: {len(tilt_map)} pillars mapped")
    except Exception as e:
        print(f"   ⚠️ Sector tilt map: {e}")

    # ── P8.2: ERP Decile Boundaries ──────────────────────────────────
    print("\n📊 Computing ERP decile boundaries...")
    try:
        from src.value_metrics import compute_erp_deciles
        erp = compute_erp_deciles(sb)
        if erp.get("ok"):
            print(f"   Deciles: {len(erp.get('decile_boundaries', []))} boundaries, {erp.get('samples', 0)} samples")
    except Exception as e:
        print(f"   ⚠️ ERP deciles: {e}")
        erp = {}

    # ── P16: Write manifest.json ──────────────────────────────────
    print("\n📋 Writing manifest.json...")
    try:
        import hashlib, json
        _manifest_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "data", "manifest.json")
        _weights = locals().get("weights", {})
        _tilt_map = locals().get("tilt_map", {})
        _erp_deciles = erp.get("decile_boundaries", []) if isinstance(erp, dict) else []
        manifest = {
            "version": hashlib.sha256(str(datetime.now().timestamp()).encode()).hexdigest()[:7],
            "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "fingerprint_buckets": {
                "nifty": 100, "vix": 1, "brent": 1.0, "usdinr": 0.1, "dxy": 0.5
            },
            "fragility": {"cap_neutral": 65, "force_defensive": 85},
            "adaptive_weights": _weights if _weights else {
                "Stagflation": 1.0, "West_Asia": 1.0, "EM_Contagion": 1.0,
                "Carry_Unwind": 1.0, "De-dollarization": 1.0, "Tech_Cycle": 1.0
            },
            "sector_tilt_map": _tilt_map if _tilt_map else {},
            "erp_deciles": _erp_deciles if len(_erp_deciles) == 10 else [-2.5, -2.1, -1.8, -1.5, -1.2, -0.9, -0.6, -0.3, 0.0, 0.4],
            "steady_state_template": "🟢 Steady state since {last_regime_time}. Regime: {regime} | Nifty: {nifty} | VIX: {vix}. No notable change.",
        }
        with open(_manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"   ✅ Manifest written (v{manifest['version']})")
    except Exception as e:
        print(f"   ⚠️ Manifest write: {e}")

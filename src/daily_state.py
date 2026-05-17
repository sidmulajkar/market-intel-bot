"""
Daily State Machine — Inter-job communication via Supabase.
Each job reads/writes daily state so they know what happened before.

Uses bot_state table with key pattern: daily_state_YYYY-MM-DD
"""
import json
from datetime import datetime
from typing import Dict, List, Optional
from src.db import get_bot_state, set_bot_state


# ═══════════════════════════════════════════════════════════════════════════════
# STATE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_STATE = {
    "date": None,
    "jobs_completed": [],
    "morning_bull_bear": None,
    "morning_master_signal": None,
    "morning_fii_net": None,
    "vix_spike_detected": False,
    "threshold_alerts_fired": [],
    "prediction_stored": False,
    "options_snapshot_stored": False,
    "market_open_regime": None,
    "anomalies_detected": [],
    "last_updated": None,
}


def _state_key(date_str: str = None) -> str:
    """Get bot_state key for today's state."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    return f"daily_state_{date_str}"


# ═══════════════════════════════════════════════════════════════════════════════
# READ/WRITE
# ═══════════════════════════════════════════════════════════════════════════════

def get_daily_state(date_str: str = None) -> Dict:
    """Get today's state. Returns default if not yet created."""
    key = _state_key(date_str)
    raw = get_bot_state(key)

    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass

    # Return fresh default
    state = DEFAULT_STATE.copy()
    state["date"] = date_str or datetime.now().strftime("%Y-%m-%d")
    return state


def save_daily_state(state: Dict, date_str: str = None) -> bool:
    """Save daily state to bot_state table."""
    key = _state_key(date_str)
    state["last_updated"] = datetime.now().isoformat()
    return set_bot_state(key, json.dumps(state))


def update_daily_state(updates: Dict, date_str: str = None) -> bool:
    """Update specific fields in today's state."""
    state = get_daily_state(date_str)
    state.update(updates)
    return save_daily_state(state, date_str)


# ═══════════════════════════════════════════════════════════════════════════════
# JOB COMPLETION TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

def mark_job_completed(job_name: str, findings: Dict = None, date_str: str = None) -> bool:
    """Mark a job as completed and store its findings."""
    state = get_daily_state(date_str)

    if job_name not in state["jobs_completed"]:
        state["jobs_completed"].append(job_name)

    # Store job-specific findings
    if findings:
        state[f"{job_name}_findings"] = findings

    return save_daily_state(state, date_str)


def is_job_completed(job_name: str, date_str: str = None) -> bool:
    """Check if a job has already run today."""
    state = get_daily_state(date_str)
    return job_name in state["jobs_completed"]


def get_job_findings(job_name: str, date_str: str = None) -> Optional[Dict]:
    """Get findings from a previously completed job."""
    state = get_daily_state(date_str)
    return state.get(f"{job_name}_findings")


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT FOR CURRENT JOB
# ═══════════════════════════════════════════════════════════════════════════════

def get_today_context() -> Dict:
    """
    Get summary of what's happened today so far.
    Used by current job to know context.
    """
    state = get_daily_state()

    context = {
        "date": state["date"],
        "jobs_run": state["jobs_completed"],
        "jobs_remaining": [],
        "alerts_today": state["threshold_alerts_fired"],
        "vix_spike": state["vix_spike_detected"],
        "anomalies": state["anomalies_detected"],
    }

    # Determine what's happened
    if "morning_brief" in state["jobs_completed"]:
        findings = state.get("morning_brief_findings", {})
        context["morning_signal"] = findings.get("master_signal") or state.get("morning_master_signal")
        context["morning_bull_bear"] = findings.get("bull_bear") or state.get("morning_bull_bear")

    if state.get("prediction_stored"):
        context["prediction_available"] = True

    return context


def format_today_context(context: Dict) -> str:
    """Format today's context for AI prompt injection."""
    if not context.get("jobs_run"):
        return ""

    lines = [f"[Today's Context — {context['date']}]"]
    lines.append(f"  Jobs completed: {', '.join(context['jobs_run'])}")

    if context.get("morning_signal"):
        lines.append(f"  Morning signal: {context['morning_signal']}")
    if context.get("alerts_today"):
        lines.append(f"  Alerts fired: {', '.join(context['alerts_today'])}")
    if context.get("vix_spike"):
        lines.append(f"  ⚠️ VIX spike detected today")
    if context.get("anomalies"):
        lines.append(f"  Anomalies: {', '.join(context['anomalies'])}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test state machine
    state = get_daily_state()
    print(f"Initial state: {state}")

    mark_job_completed("fii_fetch", {"fii_net": -1500})
    mark_job_completed("morning_brief", {"master_signal": "BEARISH"})

    context = get_today_context()
    print(f"\nContext: {context}")
    print(f"\n{format_today_context(context)}")

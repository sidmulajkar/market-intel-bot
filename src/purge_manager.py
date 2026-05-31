"""
Centralized retention policy for all Supabase tables.
Single source of truth — imported by sunday_backfill.py and db.py.

Three categories:
  HISTORICAL  — archived to CSV then purged (two-phase: archived=true AND age > retention)
  OPERATIONAL — time-based purge only (no CSV archive needed)
  REFERENCE   — never purged (static/config data)

Table naming convention: matches Supabase table names exactly.
"""
from datetime import datetime, timedelta
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# RETENTION_POLICY
# ─────────────────────────────────────────────────────────────────────────────
# archive_to_csv:  Sunday backfill writes this table's data to a CSV
# purge_archived:  Delete rows that are BOTH archived=True AND older than retention_days
#                  (two-phase commit gate — row must be in CSV before deletion)
# date_col:        Primary date column used for age cutoff
# retention_days:  None = never purge; 0 = immediate; N = delete rows older than N days

RETENTION_POLICY = {

    # ── HISTORICAL TABLES (archive to CSV, then purge from DB) ──────────────
    # Data flows: live → Supabase (today) → Sunday CSV archive → Supabase purge
    # archived=true is set by sunday_backfill.py after CSV write succeeds.
    # Purge only deletes rows that are: (a) archived=True AND (b) >retention_days old

    "macro_anchor_snapshots": {
        "retention_days": 365,
        "date_col": "trade_date",
        "archive_to_csv": True,
        "purge_archived": True,
        "description": "Daily macro anchor snapshots — kept 1Y in DB for /commands",
    },
    "fii_dii_flows": {
        "retention_days": 365,
        "date_col": "date",
        "archive_to_csv": True,
        "purge_archived": True,
        "description": "FII/DII daily flows — kept 1Y for clone engine + flow velocity",
    },
    "market_breadth_history": {
        "retention_days": 365,
        "date_col": "date",
        "archive_to_csv": True,
        "purge_archived": True,
        "description": "A/D breadth data — archived alongside nifty_history.csv",
    },
    "options_snapshots": {
        "retention_days": 7,
        "date_col": "trade_date",
        "archive_to_csv": False,   # options_history.csv not in scope yet
        "purge_archived": False,
        "description": "Daily PCR/GEX/skew — short retention, not worth CSV overhead",
    },
    "stress_history": {
        "retention_days": 180,
        "date_col": "trade_date",
        "archive_to_csv": True,
        "purge_archived": True,
        "description": "Stress index scores — 6mo for backtesting",
    },
    "valuation_history": {
        "retention_days": 365,
        "date_col": "trade_date",
        "archive_to_csv": True,
        "purge_archived": True,
        "description": "P/E, P/B, risk premium history — 1Y for valuation context",
    },

    # ── OPERATIONAL TABLES (time-based purge only, no CSV archive) ──────────
    # Transient state — no CSV archive needed, direct DELETE by age

    "market_state": {
        "retention_days": 90,
        "date_col": "trade_date",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "Regime/stress JSONB state — 90d for scorecard + overrides",
    },
    "analysis_cache": {
        "retention_days": 7,
        "date_col": "expires_at",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "AI cache — stale after a week",
    },
    "sent_alerts": {
        "retention_days": 30,
        "date_col": "date",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "Alert log — 1 month for audit trail",
    },
    "forecast_log": {
        "retention_days": 90,
        "date_col": "date",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "Brier score calibration — 90d sufficient",
    },
    "clone_history": {
        "retention_days": 180,
        "date_col": "trade_date",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "Clone match history — 6mo for regime backtesting",
    },
    "signal_accuracy_log": {
        "retention_days": 365,
        "date_col": "date",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "Signal accuracy log — 1Y for Brier score calibration",
    },
    "prediction_outcomes": {
        "retention_days": 90,
        "date_col": "prediction_date",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "Prediction outcomes — 90d for scorecard",
    },
    "analytics_ledger": {
        "retention_days": 90,
        "date_col": "date",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "Misc analytics ledger — 90d",
    },
    "cftc_positioning_history": {
        "retention_days": 270,
        "date_col": "date",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "CFTC weekly data — 9mo (~39 rows) minimum for signals",
    },
    "factor_scores_history": {
        "retention_days": 180,
        "date_col": "date",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "Factor attribution scores — 6mo for rotation patterns",
    },
    "sector_rs_history": {
        "retention_days": 180,
        "date_col": "date",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "Sector RS history — 6mo for rotation analysis",
    },
    "market_internals_history": {
        "retention_days": 180,
        "date_col": "date",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "Market internals (new highs/lows/breadth) — 6mo",
    },
    "corporate_actions": {
        "retention_days": 90,
        "date_col": "ex_date",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "Corporate actions — refreshed weekly, 90d retention",
    },
    "earnings_surprises": {
        "retention_days": 730,
        "date_col": "date",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "Earnings surprises — 2Y (8 quarters across Nifty 50)",
    },
    "mf_watchlist": {
        "retention_days": None,
        "date_col": "added_at",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "MF watchlist — reference table, never purged",
    },
    "watchlist": {
        "retention_days": None,
        "date_col": "added_at",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "Watchlist — reference table, never purged",
    },
    "bot_state": {
        "retention_days": None,
        "date_col": "updated_at",
        "archive_to_csv": False,
        "purge_archived": False,
        "description": "Key-value config — reference table, never purged",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# PURGE FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def purge_expired_tables(supabase_client, dry_run: bool = False) -> dict:
    """
    Purge expired rows from all tables based on RETENTION_POLICY.

    Called by sunday_backfill.run() AFTER CSV push succeeds.
    Also called by db.purge_old_data() for operational tables.

    Two-phase for historical tables:
      DELETE FROM table
      WHERE trade_date < cutoff AND archived = true

    Direct delete for operational tables:
      DELETE FROM table
      WHERE date_col < cutoff

    Args:
        supabase_client: Supabase client instance
        dry_run: If True, returns counts without deleting

    Returns: {"table_name": rows_deleted, ...}  (errors prefixed with "ERROR:")
    """
    results = {}
    now = datetime.utcnow()

    for table_name, policy in RETENTION_POLICY.items():
        retention_days = policy.get("retention_days")
        if retention_days is None:
            continue  # Never purge

        date_col = policy.get("date_col", "date")
        cutoff = now - timedelta(days=retention_days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        try:
            query = supabase_client.table(table_name).delete()

            if policy.get("purge_archived"):
                # Two-phase: only delete rows that are BOTH archived AND expired
                query = query.lt(date_col, cutoff_str).eq("archived", True)
            else:
                # Direct: delete rows older than retention period
                # Handle datetime vs date column types
                if date_col == "expires_at":
                    query = query.lt(date_col, cutoff.isoformat())
                else:
                    query = query.lt(date_col, cutoff_str)

            if dry_run:
                # Simulate count without deleting
                sel = supabase_client.table(table_name).select(date_col, count="exact")
                if policy.get("purge_archived"):
                    sel = sel.lt(date_col, cutoff_str).eq("archived", True)
                else:
                    sel = sel.lt(date_col, cutoff_str)
                count_result = sel.execute()
                results[table_name] = count_result.count if hasattr(count_result, "count") else 0
            else:
                result = query.execute()
                results[table_name] = len(result.data) if result.data else 0

        except Exception as e:
            results[table_name] = f"ERROR: {e}"

    return results


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_retention_days(table_name: str) -> Optional[int]:
    """Return retention_days for a table, or None if never purged."""
    policy = RETENTION_POLICY.get(table_name)
    return policy.get("retention_days") if policy else None


def is_historical_table(table_name: str) -> bool:
    """Return True if this table is archived to CSV on Sundays."""
    policy = RETENTION_POLICY.get(table_name)
    return policy.get("archive_to_csv", False) if policy else False


def archive_tables() -> list:
    """Return list of table names that should be archived to CSV."""
    return [t for t, p in RETENTION_POLICY.items() if p.get("archive_to_csv")]
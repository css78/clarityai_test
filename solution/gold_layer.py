"""
gold_layer.py
=============
Gold layer — join, enrichment and DS view as pure functions.

upsert_csv is imported directly from silver_layer (DRY — no inheritance).
Each function has a single responsibility and is independently testable.
"""

from pathlib import Path

import pandas as pd

from config import (
    GOLD_PATH,
    MERGE_KEYS,
    SILVER_PATHS,
    TECH_FIELDS,
)
from silver_layer import upsert_csv


# ---------------------------------------------------------------------------
# Join
# ---------------------------------------------------------------------------

def build_wide_dataframe() -> pd.DataFrame:
    """Joins all Silver tables into a single wide Gold DataFrame.

    Performs FULL OUTER merges so movies present in only a subset of
    providers are retained with NaN for missing fields.

    domestic_box_office conflict resolution:
        Provider 3 is the truth source; Provider 2 is the fallback.
        Resolved via combine_first() — equivalent to SQL COALESCE.

    Returns:
        Wide DataFrame with one row per (movie_title, release_year).
    """
    def read(key: str) -> pd.DataFrame:
        return pd.read_csv(SILVER_PATHS[key], dtype=str)

    p1  = read("provider1")[MERGE_KEYS + ["critic_score_pct", "top_critic_score", "total_critic_reviews"]]
    p2  = read("provider2")[MERGE_KEYS + ["audience_avg_score", "total_audience_ratings", "domestic_box_office"]].rename(columns={"domestic_box_office": "_dom_p2"})
    p3d = read("provider3_domestic")[MERGE_KEYS + ["domestic_box_office"]].rename(columns={"domestic_box_office": "_dom_p3"})
    p3i = read("provider3_international")[MERGE_KEYS + ["international_box_office"]]
    p3f = read("provider3_financials")[MERGE_KEYS + ["production_budget", "marketing_spend"]]

    df = p1
    for frame in [p2, p3d, p3i, p3f]:
        df = df.merge(frame, on=MERGE_KEYS, how="outer")

    # P3 wins; P2 is fallback when P3 is NaN
    df["domestic_box_office"] = df["_dom_p3"].combine_first(df["_dom_p2"])
    return df.drop(columns=["_dom_p2", "_dom_p3"])


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------

def _to_num(df: pd.DataFrame, col: str) -> pd.Series:
    """Coerces a column to numeric; non-numeric values become NaN."""
    return pd.to_numeric(df[col], errors="coerce")


def add_total_box_office(df: pd.DataFrame) -> pd.DataFrame:
    """Adds total_box_office = domestic + international.

    Args:
        df: Gold DataFrame.

    Returns:
        DataFrame with total_box_office column added.
    """
    df = df.copy()
    df["total_box_office"] = _to_num(df, "domestic_box_office") + _to_num(df, "international_box_office")
    return df


def add_total_investment(df: pd.DataFrame) -> pd.DataFrame:
    """Adds total_investment = production_budget + marketing_spend.

    Args:
        df: Gold DataFrame.

    Returns:
        DataFrame with total_investment column added.
    """
    df = df.copy()
    df["total_investment"] = _to_num(df, "production_budget") + _to_num(df, "marketing_spend")
    return df


def add_roi(df: pd.DataFrame) -> pd.DataFrame:
    """Adds roi = (total_box_office - total_investment) / total_investment.

    Returns NaN when total_investment is zero or NaN to prevent
    division-by-zero errors.

    Args:
        df: Gold DataFrame with total_box_office and total_investment.

    Returns:
        DataFrame with roi column added.
    """
    df   = df.copy()
    inv  = pd.to_numeric(df["total_investment"], errors="coerce")
    bo   = pd.to_numeric(df["total_box_office"],  errors="coerce")
    safe = inv.where(inv.notna() & (inv != 0), other=float("nan"))
    df["roi"] = ((bo - safe) / safe).round(4)
    return df


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Applies all calculated fields to the Gold DataFrame.

    Runs: total_box_office → total_investment → roi (order matters).

    Args:
        df: Wide Gold DataFrame from build_wide_dataframe().

    Returns:
        DataFrame with all three calculated columns added.
    """
    df = add_total_box_office(df)
    df = add_total_investment(df)
    df = add_roi(df)
    return df


# ---------------------------------------------------------------------------
# DS view
# ---------------------------------------------------------------------------

def get_ds_view(gold_path: Path = GOLD_PATH) -> pd.DataFrame:
    """Returns the Gold table without technical audit columns.

    Args:
        gold_path: Path to the Gold CSV (injectable for tests).

    Returns:
        DataFrame with only business and calculated columns.

    Raises:
        FileNotFoundError: If the Gold CSV does not exist.
    """
    if not gold_path.exists():
        raise FileNotFoundError(
            f"Gold table not found at: '{gold_path}'. "
            "Run the Gold layer first."
        )
    df = pd.read_csv(gold_path, dtype=str)
    return df[[c for c in df.columns if c not in TECH_FIELDS]]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_gold() -> pd.DataFrame:
    """Runs the Gold layer: join → enrich → write → DS view.

    Returns:
        Data Scientists view DataFrame (no technical columns).
    """
    print("\nGold layer — starting build\n")

    df = build_wide_dataframe()
    df = enrich(df)
    upsert_csv(df, GOLD_PATH)
    print(f"Gold table written → {GOLD_PATH}")

    view = get_ds_view()
    print(f"DS view ready — {len(view.columns)} columns, {len(view)} rows")
    print(f"\n── Gold summary ────────────────────────────────────")
    print(f"Wide CSV : {GOLD_PATH}")
    return view

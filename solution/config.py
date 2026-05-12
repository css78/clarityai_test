"""
config.py
=========
Single source of truth for all pipeline constants, paths and mappings.

Kept intentionally flat: plain dicts and Path constants.
No classes, no logic — just data.
"""

from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Root paths
# ---------------------------------------------------------------------------
BASE_DIR:     Path = Path("C:/myprojects/clarityai_exercise")
DATA_DIR:     Path = BASE_DIR / "data"
SOLUTION_DIR: Path = BASE_DIR / "solution"
OUTPUT_DIR:   Path = SOLUTION_DIR / "output"
CONTROL_DIR:  Path = SOLUTION_DIR / "control"

# ---------------------------------------------------------------------------
# Input paths
# ---------------------------------------------------------------------------
INPUT_PATHS: dict[str, Path] = {
    "provider1":               DATA_DIR / "provider1.csv",
    "provider2":               DATA_DIR / "provider2.json",
    "provider3_domestic":      DATA_DIR / "provider3_domestic.csv",
    "provider3_international": DATA_DIR / "provider3_international.csv",
    "provider3_financials":    DATA_DIR / "provider3_financials.csv",
}

# ---------------------------------------------------------------------------
# Bronze output roots — partitioned by ingestion_date at write time
# ---------------------------------------------------------------------------
BRONZE_PATHS: dict[str, Path] = {
    "provider1":               OUTPUT_DIR / "bronze" / "provider1",
    "provider2":               OUTPUT_DIR / "bronze" / "provider2",
    "provider3_domestic":      OUTPUT_DIR / "bronze" / "provider3" / "domestic",
    "provider3_international": OUTPUT_DIR / "bronze" / "provider3" / "international",
    "provider3_financials":    OUTPUT_DIR / "bronze" / "provider3" / "financials",
}

# ---------------------------------------------------------------------------
# Silver output paths — one flat CSV per provider
# ---------------------------------------------------------------------------
SILVER_PATHS: dict[str, Path] = {
    "provider1":               OUTPUT_DIR / "silver" / "provider1.csv",
    "provider2":               OUTPUT_DIR / "silver" / "provider2.csv",
    "provider3_domestic":      OUTPUT_DIR / "silver" / "provider3_domestic.csv",
    "provider3_international": OUTPUT_DIR / "silver" / "provider3_international.csv",
    "provider3_financials":    OUTPUT_DIR / "silver" / "provider3_financials.csv",
}

# ---------------------------------------------------------------------------
# Gold output path
# ---------------------------------------------------------------------------
GOLD_PATH: Path = OUTPUT_DIR / "gold" / "movies.csv"

# ---------------------------------------------------------------------------
# Control log
# ---------------------------------------------------------------------------
LOG_PATH: Path = CONTROL_DIR / "last_ingestion_log.json"

# ---------------------------------------------------------------------------
# Pipeline constants
# ---------------------------------------------------------------------------
TODAY:          str          = date.today().strftime("%Y-%m-%d")
MERGE_KEYS:     list[str]    = ["movie_title", "release_year"]
TECH_FIELDS:    frozenset    = frozenset({"insertion_timestamp", "update_timestamp", "ingestion_date"})
NULL_YEAR:      str          = "N/A"

# ---------------------------------------------------------------------------
# Ingestion frequency in days per provider
# ---------------------------------------------------------------------------
FREQUENCIES: dict[str, int] = {
    "provider1":               7,
    "provider2":               15,
    "provider3_domestic":      30,
    "provider3_international": 30,
    "provider3_financials":    30,
}

# ---------------------------------------------------------------------------
# Provider keys (ordered for pipeline execution)
# ---------------------------------------------------------------------------
PROVIDERS: list[str] = [
    "provider1",
    "provider2",
    "provider3_domestic",
    "provider3_international",
    "provider3_financials",
]

# ---------------------------------------------------------------------------
# Silver rename maps — {bronze_column: silver_column}
# ---------------------------------------------------------------------------
RENAME_MAPS: dict[str, dict[str, str]] = {
    "provider1": {
        "movie_title":                  "movie_title",
        "release_year":                 "release_year",
        "critic_score_percentage":      "critic_score_pct",
        "top_critic_score":             "top_critic_score",
        "total_critic_reviews_counted": "total_critic_reviews",
    },
    "provider2": {
        "title":                     "movie_title",
        "year":                      "release_year",
        "audience_average_score":    "audience_avg_score",
        "total_audience_ratings":    "total_audience_ratings",
        "domestic_box_office_gross": "domestic_box_office",
    },
    "provider3_domestic": {
        "film_name":            "movie_title",
        "year_of_release":      "release_year",
        "box_office_gross_usd": "domestic_box_office",
    },
    "provider3_international": {
        "film_name":            "movie_title",
        "year_of_release":      "release_year",
        "box_office_gross_usd": "international_box_office",
    },
    "provider3_financials": {
        "film_name":             "movie_title",
        "year_of_release":       "release_year",
        "production_budget_usd": "production_budget",
        "marketing_spend_usd":   "marketing_spend",
    },
}

# ---------------------------------------------------------------------------
# Silver cast targets — {silver_column: pandas_dtype}
# Only columns that need casting are listed; all others stay as str.
# ---------------------------------------------------------------------------
CAST_MAPS: dict[str, dict[str, str]] = {
    "provider1": {
        "critic_score_pct":     "Int64",
        "top_critic_score":     "float64",
        "total_critic_reviews": "Int64",
    },
    "provider2": {
        "audience_avg_score":    "float64",
        "total_audience_ratings":"Int64",
        "domestic_box_office":   "Int64",
    },
    "provider3_domestic":      {"domestic_box_office":     "Int64"},
    "provider3_international": {"international_box_office": "Int64"},
    "provider3_financials": {
        "production_budget": "Int64",
        "marketing_spend":   "Int64",
    },
}

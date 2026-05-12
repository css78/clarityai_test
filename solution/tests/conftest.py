"""
conftest.py — shared fixtures for the test suite.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture()
def bronze_p1() -> pd.DataFrame:
    """Minimal Bronze DataFrame for provider1 (all str)."""
    return pd.DataFrame({
        "movie_title":                  ["Inception", "The Dark Knight"],
        "release_year":                 ["2010",       "2008"],
        "critic_score_percentage":      ["87",         "94"],
        "top_critic_score":             ["8.1",        "8.6"],
        "total_critic_reviews_counted": ["450",        "350"],
        "ingestion_date":               ["2026-05-10", "2026-05-10"],
    })


@pytest.fixture()
def silver_p1() -> pd.DataFrame:
    """Minimal Silver DataFrame for provider1 (typed, standard names)."""
    return pd.DataFrame({
        "movie_title":          ["Inception", "The Dark Knight"],
        "release_year":         ["2010",       "2008"],
        "critic_score_pct":     [87,           94],
        "top_critic_score":     [8.1,          8.6],
        "total_critic_reviews": [450,          350],
        "ingestion_date":       ["2026-05-10", "2026-05-10"],
    })


@pytest.fixture()
def gold_df() -> pd.DataFrame:
    """Minimal Gold DataFrame with financial data for enrichment tests."""
    return pd.DataFrame({
        "movie_title":             ["Inception",   "The Dark Knight", "Parasite"],
        "release_year":            ["2010",        "2008",            "2019"],
        "domestic_box_office":     [292576195,     533345358,         53369749],
        "international_box_office":[535700000,     469700000,         None],
        "production_budget":       [160000000,     185000000,         None],
        "marketing_spend":         [100000000,     150000000,         None],
    })

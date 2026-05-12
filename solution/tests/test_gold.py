"""
test_gold.py — tests for gold_layer.py functions.
"""
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from gold_layer import (
    add_roi,
    add_total_box_office,
    add_total_investment,
    build_wide_dataframe,
    enrich,
    get_ds_view,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_silver_csvs(tmp_path: Path) -> dict[str, Path]:
    """Writes all five Silver CSVs to tmp_path."""
    paths = {
        "provider1":               tmp_path / "provider1.csv",
        "provider2":               tmp_path / "provider2.csv",
        "provider3_domestic":      tmp_path / "provider3_domestic.csv",
        "provider3_international": tmp_path / "provider3_international.csv",
        "provider3_financials":    tmp_path / "provider3_financials.csv",
    }

    pd.DataFrame({
        "movie_title": ["Inception", "The Dark Knight", "Parasite"],
        "release_year": ["2010", "2008", "2019"],
        "critic_score_pct": ["87", "94", "99"],
        "top_critic_score": ["8.1", "8.6", "9.5"],
        "total_critic_reviews": ["450", "350", "475"],
    }).to_csv(paths["provider1"], index=False)

    pd.DataFrame({
        "movie_title": ["Inception", "The Dark Knight", "Parasite"],
        "release_year": ["2010", "2008", "2019"],
        "audience_avg_score": ["9.1", "9.4", "9.0"],
        "total_audience_ratings": ["1500000", "2200000", "800000"],
        "domestic_box_office": ["999999999", "999999999", "53369749"],  # wrong P2 values
    }).to_csv(paths["provider2"], index=False)

    pd.DataFrame({
        "movie_title": ["Inception", "The Dark Knight"],
        "release_year": ["2010", "2008"],
        "domestic_box_office": ["292576195", "533345358"],
    }).to_csv(paths["provider3_domestic"], index=False)

    pd.DataFrame({
        "movie_title": ["Inception", "The Dark Knight"],
        "release_year": ["2010", "2008"],
        "international_box_office": ["535700000", "469700000"],
    }).to_csv(paths["provider3_international"], index=False)

    pd.DataFrame({
        "movie_title": ["Inception", "The Dark Knight"],
        "release_year": ["2010", "2008"],
        "production_budget": ["160000000", "185000000"],
        "marketing_spend": ["100000000", "150000000"],
    }).to_csv(paths["provider3_financials"], index=False)

    return paths


# ---------------------------------------------------------------------------
# build_wide_dataframe
# ---------------------------------------------------------------------------

class TestBuildWideDataframe:

    def test_retains_parasite_absent_from_p3(self, tmp_path):
        paths = _make_silver_csvs(tmp_path)
        with patch("gold_layer.SILVER_PATHS", paths):
            df = build_wide_dataframe()
        assert "Parasite" in df["movie_title"].values

    def test_p3_wins_over_p2_for_domestic(self, tmp_path):
        paths = _make_silver_csvs(tmp_path)
        with patch("gold_layer.SILVER_PATHS", paths):
            df = build_wide_dataframe()
        inception = df[df["movie_title"] == "Inception"]
        assert float(inception["domestic_box_office"].iloc[0]) == 292576195

    def test_p2_used_as_fallback_when_p3_absent(self, tmp_path):
        paths = _make_silver_csvs(tmp_path)
        with patch("gold_layer.SILVER_PATHS", paths):
            df = build_wide_dataframe()
        parasite = df[df["movie_title"] == "Parasite"]
        assert float(parasite["domestic_box_office"].iloc[0]) == 53369749


# ---------------------------------------------------------------------------
# add_total_box_office
# ---------------------------------------------------------------------------

class TestAddTotalBoxOffice:

    def test_sums_correctly(self, gold_df):
        result = add_total_box_office(gold_df)
        assert result["total_box_office"].iloc[0] == 292576195 + 535700000

    def test_nan_when_international_missing(self, gold_df):
        result = add_total_box_office(gold_df)
        assert pd.isna(result["total_box_office"].iloc[2])  # Parasite


# ---------------------------------------------------------------------------
# add_total_investment
# ---------------------------------------------------------------------------

class TestAddTotalInvestment:

    def test_sums_correctly(self, gold_df):
        result = add_total_investment(gold_df)
        assert result["total_investment"].iloc[0] == 160000000 + 100000000

    def test_nan_when_budget_missing(self, gold_df):
        result = add_total_investment(gold_df)
        assert pd.isna(result["total_investment"].iloc[2])  # Parasite


# ---------------------------------------------------------------------------
# add_roi
# ---------------------------------------------------------------------------

class TestAddRoi:

    def _with_totals(self, bo, inv) -> pd.DataFrame:
        return pd.DataFrame({
            "movie_title":    ["Inception"],
            "release_year":   ["2010"],
            "total_box_office":  [bo],
            "total_investment":  [inv],
        })

    def test_calculates_correctly(self):
        df     = self._with_totals(828276195, 260000000)
        result = add_roi(df)
        assert abs(result["roi"].iloc[0] - 2.1857) < 0.001

    def test_nan_when_investment_is_zero(self):
        result = add_roi(self._with_totals(100000000, 0))
        assert pd.isna(result["roi"].iloc[0])

    def test_nan_when_investment_is_nan(self):
        result = add_roi(self._with_totals(100000000, float("nan")))
        assert pd.isna(result["roi"].iloc[0])


# ---------------------------------------------------------------------------
# enrich
# ---------------------------------------------------------------------------

class TestEnrich:

    def test_adds_all_three_columns(self, gold_df):
        result = enrich(gold_df)
        assert "total_box_office" in result.columns
        assert "total_investment"  in result.columns
        assert "roi"               in result.columns

    def test_inception_roi_is_positive(self, gold_df):
        result  = enrich(gold_df)
        roi_val = result[result["movie_title"] == "Inception"]["roi"].iloc[0]
        assert roi_val > 0

    def test_parasite_roi_is_nan(self, gold_df):
        result  = enrich(gold_df)
        roi_val = result[result["movie_title"] == "Parasite"]["roi"].iloc[0]
        assert pd.isna(roi_val)


# ---------------------------------------------------------------------------
# get_ds_view
# ---------------------------------------------------------------------------

class TestGetDsView:

    def _write_gold(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({
            "movie_title":         ["Inception"],
            "release_year":        ["2010"],
            "roi":                 ["2.1857"],
            "ingestion_date":      ["2026-05-10"],
            "insertion_timestamp": ["2026-05-10T10:00:00"],
            "update_timestamp":    ["2026-05-10T10:00:00"],
        }).to_csv(path, index=False)

    def test_excludes_technical_fields(self, tmp_path):
        path = tmp_path / "movies.csv"
        self._write_gold(path)
        with patch("gold_layer.GOLD_PATH", path):
            view = get_ds_view(path)
        for field in ["insertion_timestamp", "update_timestamp", "ingestion_date"]:
            assert field not in view.columns

    def test_retains_business_columns(self, tmp_path):
        path = tmp_path / "movies.csv"
        self._write_gold(path)
        with patch("gold_layer.GOLD_PATH", path):
            view = get_ds_view(path)
        for col in ["movie_title", "release_year", "roi"]:
            assert col in view.columns

    def test_raises_when_file_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Gold table not found"):
            get_ds_view(tmp_path / "missing.csv")

    def test_filterable_by_title(self, tmp_path):
        path = tmp_path / "movies.csv"
        self._write_gold(path)
        with patch("gold_layer.GOLD_PATH", path):
            view = get_ds_view(path)
        assert len(view[view["movie_title"] == "Inception"]) == 1

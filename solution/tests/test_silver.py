"""
test_silver.py — tests for silver_layer.py functions.
"""
import time
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from silver_layer import (
    apply_year_fallback,
    cast_columns,
    clean,
    read_latest_partition,
    rename_columns,
    transform_provider,
    trim_strings,
    upsert_csv,
)


# ---------------------------------------------------------------------------
# rename_columns
# ---------------------------------------------------------------------------

class TestRenameColumns:

    def test_renames_present_columns(self):
        df = pd.DataFrame({"film_name": ["Inception"], "year_of_release": ["2010"]})
        result = rename_columns(df, {"film_name": "movie_title", "year_of_release": "release_year"})
        assert "movie_title"     in result.columns
        assert "film_name"       not in result.columns
        assert "release_year"    in result.columns
        assert "year_of_release" not in result.columns

    def test_ignores_absent_keys(self):
        df = pd.DataFrame({"film_name": ["Inception"]})
        result = rename_columns(df, {"film_name": "movie_title", "nonexistent": "other"})
        assert "movie_title" in result.columns


# ---------------------------------------------------------------------------
# trim_strings
# ---------------------------------------------------------------------------

class TestTrimStrings:

    def test_strips_whitespace(self):
        df = pd.DataFrame({"title": ["  Inception  "], "score": ["  87  "]})
        result = trim_strings(df)
        assert result["title"].iloc[0] == "Inception"
        assert result["score"].iloc[0] == "87"


# ---------------------------------------------------------------------------
# cast_columns
# ---------------------------------------------------------------------------

class TestCastColumns:

    def test_casts_to_int64(self):
        df = pd.DataFrame({"score": ["87"]})
        result = cast_columns(df, {"score": "Int64"})
        assert result["score"].iloc[0] == 87

    def test_failed_cast_produces_nan(self):
        df = pd.DataFrame({"score": ["not_a_number"]})
        result = cast_columns(df, {"score": "Int64"})
        assert pd.isna(result["score"].iloc[0])

    def test_casts_to_float64(self):
        df = pd.DataFrame({"score": ["8.1"]})
        result = cast_columns(df, {"score": "float64"})
        assert abs(result["score"].iloc[0] - 8.1) < 0.001

    def test_skips_absent_columns(self):
        df = pd.DataFrame({"title": ["Inception"]})
        result = cast_columns(df, {"absent_col": "Int64"})
        assert "title" in result.columns


# ---------------------------------------------------------------------------
# apply_year_fallback
# ---------------------------------------------------------------------------

class TestApplyYearFallback:

    def test_replaces_null_with_na(self):
        df = pd.DataFrame({"release_year": [None]})
        result = apply_year_fallback(df)
        assert result["release_year"].iloc[0] == "N/A"

    def test_preserves_valid_year(self):
        df = pd.DataFrame({"release_year": ["2010"]})
        result = apply_year_fallback(df)
        assert result["release_year"].iloc[0] == "2010"


# ---------------------------------------------------------------------------
# clean (full pipeline)
# ---------------------------------------------------------------------------

class TestClean:

    def test_full_pipeline(self):
        df = pd.DataFrame({
            "film_name":       ["  Inception  "],
            "year_of_release": [None],
            "score":           ["  87  "],
        })
        result = clean(
            df,
            rename_map={"film_name": "movie_title", "year_of_release": "release_year", "score": "score"},
            cast_map={"score": "Int64"},
        )
        assert result["movie_title"].iloc[0]  == "Inception"
        assert result["release_year"].iloc[0] == "N/A"
        assert result["score"].iloc[0]        == 87


# ---------------------------------------------------------------------------
# upsert_csv
# ---------------------------------------------------------------------------

class TestUpsertCsv:

    def _df(self, title="Inception", score=87) -> pd.DataFrame:
        return pd.DataFrame({
            "movie_title":  [title],
            "release_year": ["2010"],
            "score":        [score],
        })

    def test_first_write_adds_audit_columns(self, tmp_path):
        path = tmp_path / "silver.csv"
        upsert_csv(self._df(), path)
        result = pd.read_csv(path)
        assert "insertion_timestamp" in result.columns
        assert "update_timestamp"    in result.columns

    def test_preserves_insertion_timestamp(self, tmp_path):
        path = tmp_path / "silver.csv"
        upsert_csv(self._df(), path)
        ts_orig = pd.read_csv(path)["insertion_timestamp"].iloc[0]
        time.sleep(1)
        upsert_csv(self._df(score=90), path)
        ts_after = pd.read_csv(path)["insertion_timestamp"].iloc[0]
        assert ts_orig == ts_after

    def test_refreshes_update_timestamp(self, tmp_path):
        path = tmp_path / "silver.csv"
        upsert_csv(self._df(), path)
        ts_first = pd.read_csv(path)["update_timestamp"].iloc[0]
        time.sleep(1)
        upsert_csv(self._df(score=90), path)
        ts_second = pd.read_csv(path)["update_timestamp"].iloc[0]
        assert ts_second > ts_first

    def test_inserts_new_key(self, tmp_path):
        path = tmp_path / "silver.csv"
        upsert_csv(self._df("Inception"), path)
        upsert_csv(self._df("The Dark Knight"), path)
        result = pd.read_csv(path)
        assert len(result) == 2
        assert "The Dark Knight" in result["movie_title"].values


# ---------------------------------------------------------------------------
# read_latest_partition
# ---------------------------------------------------------------------------

class TestReadLatestPartition:

    def _write_partition(self, root: Path, date_str: str, key: str) -> None:
        d = root / f"ingestion_date={date_str}"
        d.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"movie_title": ["Inception"], "ingestion_date": [date_str]}).to_csv(d / f"{key}.csv", index=False)

    def test_reads_most_recent(self, tmp_path):
        root = tmp_path / "bronze" / "provider1"
        self._write_partition(root, "2026-04-01", "provider1")
        self._write_partition(root, "2026-05-10", "provider1")
        df = read_latest_partition(root, "provider1")
        assert df["ingestion_date"].iloc[0] == "2026-05-10"

    def test_raises_when_no_partitions(self, tmp_path):
        root = tmp_path / "bronze" / "provider1"
        root.mkdir(parents=True, exist_ok=True)
        with pytest.raises(FileNotFoundError, match="No Bronze partitions"):
            read_latest_partition(root, "provider1")


# ---------------------------------------------------------------------------
# transform_provider (integration)
# ---------------------------------------------------------------------------

class TestTransformProvider:

    def _write_bronze(self, root: Path, key: str) -> None:
        d = root / "ingestion_date=2026-05-10"
        d.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({
            "movie_title":                  ["Inception"],
            "release_year":                 ["2010"],
            "critic_score_percentage":      ["87"],
            "top_critic_score":             ["8.1"],
            "total_critic_reviews_counted": ["450"],
            "ingestion_date":               ["2026-05-10"],
        }).to_csv(d / f"{key}.csv", index=False)

    def test_raises_for_unknown_key(self):
        with pytest.raises(ValueError, match="unknown_key"):
            transform_provider("unknown_key")

    def test_renames_to_silver_standard(self, tmp_path):
        bronze = tmp_path / "bronze" / "provider1"
        silver = tmp_path / "silver" / "provider1.csv"
        self._write_bronze(bronze, "provider1")

        with patch("silver_layer.BRONZE_PATHS", {"provider1": bronze}), \
             patch("silver_layer.SILVER_PATHS", {"provider1": silver}):
            df = transform_provider("provider1")

        assert "critic_score_pct"     in df.columns
        assert "total_critic_reviews" in df.columns
        assert "critic_score_percentage" not in df.columns

    def test_writes_silver_csv(self, tmp_path):
        bronze = tmp_path / "bronze" / "provider1"
        silver = tmp_path / "silver" / "provider1.csv"
        self._write_bronze(bronze, "provider1")

        with patch("silver_layer.BRONZE_PATHS", {"provider1": bronze}), \
             patch("silver_layer.SILVER_PATHS", {"provider1": silver}):
            transform_provider("provider1")

        assert silver.exists()

    def test_null_year_replaced_with_na(self, tmp_path):
        bronze = tmp_path / "bronze" / "provider1"
        silver = tmp_path / "silver" / "provider1.csv"
        d = bronze / "ingestion_date=2026-05-10"
        d.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({
            "movie_title":                  ["Unknown"],
            "release_year":                 [None],
            "critic_score_percentage":      ["50"],
            "top_critic_score":             ["5.0"],
            "total_critic_reviews_counted": ["100"],
            "ingestion_date":               ["2026-05-10"],
        }).to_csv(d / "provider1.csv", index=False)

        with patch("silver_layer.BRONZE_PATHS", {"provider1": bronze}), \
             patch("silver_layer.SILVER_PATHS", {"provider1": silver}):
            df = transform_provider("provider1")

        assert df["release_year"].iloc[0] == "N/A"

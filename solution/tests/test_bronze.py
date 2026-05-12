"""
test_bronze.py — tests for bronze_layer.py functions.
"""
import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from bronze_layer import is_due, mark_ingested, ingest_provider, _read_csv, _read_json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_str(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def _write_log(path: Path, content: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content), encoding="utf-8")


# ---------------------------------------------------------------------------
# is_due
# ---------------------------------------------------------------------------

class TestIsDue:

    def test_true_when_no_log_exists(self, tmp_path):
        assert is_due("provider1", tmp_path / "log.json") is True

    def test_true_when_log_is_corrupt(self, tmp_path):
        log = tmp_path / "log.json"
        log.write_text("{ bad json }", encoding="utf-8")
        assert is_due("provider1", log) is True

    def test_true_when_elapsed_equals_frequency(self, tmp_path):
        log = tmp_path / "log.json"
        _write_log(log, {"provider1": _date_str(7)})
        assert is_due("provider1", log) is True

    def test_true_when_elapsed_exceeds_frequency(self, tmp_path):
        log = tmp_path / "log.json"
        _write_log(log, {"provider1": _date_str(10)})
        assert is_due("provider1", log) is True

    def test_false_when_elapsed_below_frequency(self, tmp_path):
        log = tmp_path / "log.json"
        _write_log(log, {"provider1": _date_str(3)})
        assert is_due("provider1", log) is False


# ---------------------------------------------------------------------------
# mark_ingested
# ---------------------------------------------------------------------------

class TestMarkIngested:

    def test_writes_today_to_log(self, tmp_path):
        log = tmp_path / "log.json"
        mark_ingested("provider1", log)
        content = json.loads(log.read_text())
        assert content["provider1"] == date.today().strftime("%Y-%m-%d")

    def test_preserves_other_providers(self, tmp_path):
        log = tmp_path / "log.json"
        _write_log(log, {"provider2": _date_str(5)})
        mark_ingested("provider1", log)
        content = json.loads(log.read_text())
        assert content["provider2"] == _date_str(5)

    def test_creates_missing_directory(self, tmp_path):
        log = tmp_path / "deep" / "nested" / "log.json"
        mark_ingested("provider1", log)
        assert log.exists()


# ---------------------------------------------------------------------------
# ingest_provider
# ---------------------------------------------------------------------------

class TestIngestProvider:

    def _make_csv(self, tmp_path: Path) -> Path:
        csv = tmp_path / "provider1.csv"
        csv.write_text(
            "movie_title,release_year,critic_score_percentage,"
            "top_critic_score,total_critic_reviews_counted\n"
            "Inception,2010,87,8.1,450\n",
            encoding="utf-8",
        )
        return csv

    def test_returns_none_when_not_due(self, tmp_path):
        log = tmp_path / "log.json"
        _write_log(log, {"provider1": date.today().strftime("%Y-%m-%d")})
        result = ingest_provider("provider1", log_path=log)
        assert result is None

    def test_returns_dataframe_when_due(self, tmp_path):
        csv    = self._make_csv(tmp_path)
        log    = tmp_path / "log.json"
        bronze = tmp_path / "bronze" / "provider1"

        with patch("bronze_layer.INPUT_PATHS", {"provider1": csv}), \
             patch("bronze_layer.BRONZE_PATHS", {"provider1": bronze}):
            result = ingest_provider("provider1", log_path=log, today="2026-05-10")

        assert result is not None
        assert "ingestion_date" in result.columns
        assert result["ingestion_date"].iloc[0] == "2026-05-10"

    def test_all_fields_are_strings(self, tmp_path):
        csv    = self._make_csv(tmp_path)
        log    = tmp_path / "log.json"
        bronze = tmp_path / "bronze" / "provider1"

        with patch("bronze_layer.INPUT_PATHS", {"provider1": csv}), \
             patch("bronze_layer.BRONZE_PATHS", {"provider1": bronze}):
            df = ingest_provider("provider1", log_path=log, today="2026-05-10")

        for col in df.columns:
            if col != "ingestion_date":
                assert df[col].dtype == object

    def test_creates_partitioned_csv(self, tmp_path):
        csv    = self._make_csv(tmp_path)
        log    = tmp_path / "log.json"
        bronze = tmp_path / "bronze" / "provider1"

        with patch("bronze_layer.INPUT_PATHS", {"provider1": csv}), \
             patch("bronze_layer.BRONZE_PATHS", {"provider1": bronze}):
            ingest_provider("provider1", log_path=log, today="2026-05-10")

        assert (bronze / "ingestion_date=2026-05-10" / "provider1.csv").exists()

    def test_mark_ingested_called_after_write(self, tmp_path):
        csv    = self._make_csv(tmp_path)
        log    = tmp_path / "log.json"
        bronze = tmp_path / "bronze" / "provider1"

        with patch("bronze_layer.INPUT_PATHS", {"provider1": csv}), \
             patch("bronze_layer.BRONZE_PATHS", {"provider1": bronze}):
            ingest_provider("provider1", log_path=log, today="2026-05-10")

        content = json.loads(log.read_text())
        assert "provider1" in content

    def test_raises_for_unknown_provider(self, tmp_path):
        with pytest.raises(ValueError, match="unknown"):
            ingest_provider("unknown", log_path=tmp_path / "log.json")

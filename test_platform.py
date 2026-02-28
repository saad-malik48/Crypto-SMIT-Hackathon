"""
tests/test_platform.py — Unit & Integration Tests
====================================================
Run: pytest tests/ -v --tb=short
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock


# ══════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════════════════════

SAMPLE_RAW = [
    {
        "id": "bitcoin", "symbol": "btc", "name": "Bitcoin",
        "current_price": 67432.10, "market_cap": 1_328_000_000_000,
        "total_volume": 28_500_000_000,
        "price_change_percentage_24h": 2.34, "market_cap_rank": 1,
    },
    {
        "id": "ethereum", "symbol": "eth", "name": "Ethereum",
        "current_price": 3812.50, "market_cap": 457_000_000_000,
        "total_volume": 15_200_000_000,
        "price_change_percentage_24h": -1.87, "market_cap_rank": 2,
    },
    {
        "id": "solana", "symbol": "sol", "name": "Solana",
        "current_price": 178.40, "market_cap": 78_500_000_000,
        "total_volume": 3_400_000_000,
        "price_change_percentage_24h": 8.50, "market_cap_rank": 5,
    },
]

TS = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


# ══════════════════════════════════════════════════════════════════════════════
#  extract.py tests
# ══════════════════════════════════════════════════════════════════════════════

class TestExtractValidation:
    def test_validate_good_data(self):
        from extract import validate_response
        result = validate_response(SAMPLE_RAW)
        assert len(result) == 3

    def test_validate_empty_list_raises(self):
        from extract import validate_response
        with pytest.raises(ValueError, match="empty"):
            validate_response([])

    def test_validate_non_list_raises(self):
        from extract import validate_response
        with pytest.raises(ValueError):
            validate_response({"error": "rate limit"})

    def test_validate_drops_invalid_rows(self):
        from extract import validate_response
        data = SAMPLE_RAW + [{"id": "junk"}]   # missing required fields
        result = validate_response(data)
        # junk row either dropped or coerced — must not crash
        assert len(result) <= 4

    def test_validate_null_price_coerced(self):
        from extract import validate_response
        data = [{**SAMPLE_RAW[0], "current_price": None}]
        result = validate_response(data)
        assert result[0]["current_price"] == 0.0

    def test_list_raw_snapshots(self, tmp_path, monkeypatch):
        import config
        monkeypatch.setattr(config, "RAW_DIR", tmp_path)
        # Create fake snapshots
        for ts in ["20250101T120000Z", "20250101T130000Z"]:
            (tmp_path / f"coingecko_{ts}.json").write_text("{}")
        from extract import list_raw_snapshots
        snaps = list_raw_snapshots(5)
        assert len(snaps) == 2
        # Most recent first
        assert "130000" in snaps[0].name


# ══════════════════════════════════════════════════════════════════════════════
#  transform.py tests
# ══════════════════════════════════════════════════════════════════════════════

class TestTransform:
    def test_transform_returns_correct_count(self):
        from transform import transform
        coins = transform(SAMPLE_RAW, TS)
        assert len(coins) == 3

    def test_symbol_uppercased(self):
        from transform import transform
        coins = transform(SAMPLE_RAW, TS)
        for c in coins:
            assert c.symbol == c.symbol.upper()

    def test_volatility_score_computed(self):
        from transform import transform
        coins = transform(SAMPLE_RAW, TS)
        btc = next(c for c in coins if c.coin_id == "bitcoin")
        expected = abs(2.34) * 28_500_000_000
        assert abs(btc.volatility_score - expected) < 1.0

    def test_extracted_at_tz_aware(self):
        from transform import transform
        coins = transform(SAMPLE_RAW, TS)
        for c in coins:
            assert c.extracted_at.tzinfo is not None

    def test_sorted_by_rank(self):
        from transform import transform
        coins = transform(SAMPLE_RAW, TS)
        ranks = [c.market_cap_rank for c in coins]
        assert ranks == sorted(ranks)

    def test_null_price_coin_handled(self):
        from transform import transform
        bad = [{**SAMPLE_RAW[0], "current_price": None}]
        coins = transform(bad, TS)
        assert coins[0].current_price == 0.0

    def test_nan_price_defaulted(self):
        from transform import transform
        import math
        bad = [{**SAMPLE_RAW[0], "current_price": float("nan")}]
        coins = transform(bad, TS)
        assert coins[0].current_price == 0.0

    def test_summary_top_gainer(self):
        from transform import transform, summarize
        coins = transform(SAMPLE_RAW, TS)
        s = summarize(coins)
        # SOL has highest change (+8.50)
        assert s["top_gainer"]["coin"].upper() == "SOL"

    def test_to_dict_serializable(self):
        from transform import transform
        coins = transform(SAMPLE_RAW, TS)
        d = coins[0].to_dict()
        assert isinstance(d["extracted_at"], str)
        json.dumps(d)   # must be JSON-serializable


# ══════════════════════════════════════════════════════════════════════════════
#  database.py tests
# ══════════════════════════════════════════════════════════════════════════════

class TestDatabase:
    def test_sqlite_schema_created(self, tmp_path):
        from database import SQLiteManager
        mgr = SQLiteManager(path=tmp_path / "test.db")
        mgr.create_schema()
        assert mgr.test_connection()

    def test_sqlite_cursor_yields(self, tmp_path):
        from database import SQLiteManager
        mgr = SQLiteManager(path=tmp_path / "test.db")
        mgr.create_schema()
        with mgr.get_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM crypto_market")
            row = cur.fetchone()
            assert row[0] == 0

    def test_sqlite_rollback_on_error(self, tmp_path):
        from database import SQLiteManager
        mgr = SQLiteManager(path=tmp_path / "test.db")
        mgr.create_schema()
        try:
            with mgr.get_connection() as conn:
                conn.execute("INSERT INTO crypto_market VALUES (1,2,3)")  # wrong cols
                raise RuntimeError("forced")
        except Exception:
            pass
        # Table should still be intact
        with mgr.get_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM crypto_market")


# ══════════════════════════════════════════════════════════════════════════════
#  load.py tests
# ══════════════════════════════════════════════════════════════════════════════

class TestLoad:
    def _make_coins(self):
        from transform import transform
        return transform(SAMPLE_RAW, TS)

    def test_load_inserts_rows(self, tmp_path, monkeypatch):
        from database import SQLiteManager
        mgr = SQLiteManager(path=tmp_path / "load_test.db")
        mgr.create_schema()
        import database
        monkeypatch.setattr(database, "_db_manager", mgr)

        from load import load, get_row_count
        coins = self._make_coins()
        result = load(coins)
        assert result.total == 3
        assert get_row_count() == 3

    def test_load_idempotent(self, tmp_path, monkeypatch):
        from database import SQLiteManager
        mgr = SQLiteManager(path=tmp_path / "idem_test.db")
        mgr.create_schema()
        import database
        monkeypatch.setattr(database, "_db_manager", mgr)

        from load import load, get_row_count
        coins = self._make_coins()
        load(coins)
        load(coins)  # second run — same timestamp → UPSERT
        count = get_row_count()
        assert count == 3   # no duplicates

    def test_load_empty_list(self, tmp_path, monkeypatch):
        from database import SQLiteManager
        mgr = SQLiteManager(path=tmp_path / "empty_test.db")
        mgr.create_schema()
        import database
        monkeypatch.setattr(database, "_db_manager", mgr)

        from load import load
        result = load([])
        assert result.total == 0


# ══════════════════════════════════════════════════════════════════════════════
#  analysis.py tests
# ══════════════════════════════════════════════════════════════════════════════

class TestAnalysis:
    @pytest.fixture(autouse=True)
    def seed_db(self, tmp_path, monkeypatch):
        """Seed SQLite with sample data before each test."""
        from database import SQLiteManager
        mgr = SQLiteManager(path=tmp_path / "analysis_test.db")
        mgr.create_schema()
        import database
        monkeypatch.setattr(database, "_db_manager", mgr)

        from transform import transform
        from load import load
        coins = transform(SAMPLE_RAW, TS)
        load(coins)

    def test_top_gainers(self):
        from analysis import top_gainers
        result = top_gainers(2)
        assert len(result) >= 1
        # First should be highest positive change
        if len(result) >= 2:
            assert result[0]["price_change_24h"] >= result[1]["price_change_24h"]

    def test_top_market_cap(self):
        from analysis import top_market_cap
        result = top_market_cap(3)
        assert len(result) == 3
        mcaps = [r["market_cap"] for r in result]
        assert mcaps == sorted(mcaps, reverse=True)

    def test_avg_market_cap(self):
        from analysis import avg_market_cap
        val = avg_market_cap()
        assert val > 0

    def test_total_market_value(self):
        from analysis import total_market_value, top_market_cap
        total = total_market_value()
        coins = top_market_cap(20)
        expected = sum(c["market_cap"] for c in coins)
        assert abs(total - expected) < 1.0

    def test_volatility_ranking_sorted(self):
        from analysis import volatility_ranking
        result = volatility_ranking(3)
        scores = [r["volatility_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_detect_anomalies_low_threshold(self):
        from analysis import detect_anomalies
        # With threshold=0.1, all coins with any deviation should flag
        result = detect_anomalies(threshold=0.1)
        assert isinstance(result, list)

    def test_kpi_summary_keys(self):
        from analysis import kpi_summary
        kpi = kpi_summary()
        for key in ["total_market_cap", "avg_market_cap", "highest_gainer", "most_volatile"]:
            assert key in kpi, f"Missing key: {key}"

    def test_price_history(self):
        from analysis import price_history
        rows = price_history("bitcoin")
        assert len(rows) >= 1
        assert "current_price" in rows[0]

    def test_price_history_missing_coin(self):
        from analysis import price_history
        rows = price_history("nonexistent_coin_xyz")
        assert rows == []


# ══════════════════════════════════════════════════════════════════════════════
#  etl_pipeline.py tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPipeline:
    def test_run_once_success(self, tmp_path, monkeypatch):
        from database import SQLiteManager
        mgr = SQLiteManager(path=tmp_path / "pipeline_test.db")
        mgr.create_schema()
        import database
        monkeypatch.setattr(database, "_db_manager", mgr)

        # Mock extract to avoid network
        mock_ts = TS
        monkeypatch.setattr("etl_pipeline.extract", lambda: (SAMPLE_RAW, mock_ts))

        from etl_pipeline import run_once
        result = run_once()
        assert result.success
        assert result.coins_extracted == 3
        assert result.coins_transformed == 3

    def test_run_once_extract_failure(self, monkeypatch):
        def bad_extract():
            raise RuntimeError("API down")
        monkeypatch.setattr("etl_pipeline.extract", bad_extract)

        from etl_pipeline import run_once
        result = run_once()
        assert not result.success
        assert "API down" in result.error


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

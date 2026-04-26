"""Cost basis metadata on enrich_ticker (mocked market data)."""

from unittest.mock import patch

import pytest

from tools import data_fetch


@pytest.fixture(autouse=True)
def clear_lru_caches():
    data_fetch.get_current_price.cache_clear()
    data_fetch.get_purchase_price_detail.cache_clear()
    data_fetch.get_sector.cache_clear()
    yield


def test_csv_basis_trusted():
    with patch.object(data_fetch, "get_current_price", return_value=100.0), patch.object(
        data_fetch, "get_sector", return_value="Technology"
    ):
        r = data_fetch.enrich_ticker("MSFT", "2020-01-01", 1, 50.0)
    assert r["cost_basis_source"] == data_fetch.COST_BASIS_CSV
    assert r["return_pct_is_estimated"] is False
    assert r["return_pct"] == 100.0


def test_historical_basis_flagged_estimated():
    with patch.object(data_fetch, "get_current_price", return_value=100.0), patch.object(
        data_fetch, "get_sector", return_value="Technology"
    ), patch.object(
        data_fetch,
        "get_purchase_price_detail",
        return_value=(50.0, data_fetch.COST_BASIS_HISTORICAL),
    ):
        r = data_fetch.enrich_ticker("MSFT", "2020-01-01", 1, None)
    assert r["cost_basis_source"] == data_fetch.COST_BASIS_HISTORICAL
    assert r["return_pct_is_estimated"] is True
    assert r["return_pct"] == 100.0


def test_unknown_flat_zero_return():
    with patch.object(data_fetch, "get_current_price", return_value=100.0), patch.object(
        data_fetch, "get_sector", return_value="Technology"
    ), patch.object(data_fetch, "get_purchase_price_detail", return_value=(None, "")):
        r = data_fetch.enrich_ticker("MSFT", "", 1, None)
    assert r["cost_basis_source"] == data_fetch.COST_BASIS_UNKNOWN_FLAT
    assert r["return_pct_is_estimated"] is True
    assert r["return_pct"] == 0.0
    assert r["buy_price"] == 100.0


def test_summarize_cost_basis():
    from tools.reporting import summarize_cost_basis

    rows = [
        {"cost_basis_source": "csv"},
        {"cost_basis_source": "csv"},
        {"cost_basis_source": "historical_close"},
    ]
    s = summarize_cost_basis(rows)
    assert s["csv"] == 2
    assert s["historical_close"] == 1


def test_rebalance_confidence_capped_when_return_estimated():
    from tools.scoring import rebalance_decision_v2

    action, reason, conf = rebalance_decision_v2(
        return_pct=5.0,
        sentiment="Positive",
        trend_label="Uptrend",
        allocation_status="Underweight",
        score=72.0,
        return_pct_is_estimated=True,
    )
    assert conf == "LOW"
    assert action in ("BUY", "HOLD", "STRONG BUY")

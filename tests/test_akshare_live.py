import os

import pytest

from src.tools import api


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_AKSHARE_LIVE") != "1",
    reason="Set RUN_AKSHARE_LIVE=1 to run live AKShare smoke tests",
)


@pytest.mark.parametrize("ticker", ["600519.SH", "000001.SZ", "300750.SZ"])
def test_live_akshare_prices(ticker):
    prices = api.get_prices(ticker, "2024-01-01", "2024-01-10")
    if not prices:
        pytest.skip("AKShare price endpoint unavailable")
    assert len(prices) > 0
    assert prices[-1].close > 0


def test_live_akshare_financial_metrics():
    metrics = api.get_financial_metrics("600519.SH", "2024-12-31", period="annual", limit=1)
    if not metrics:
        pytest.skip("AKShare financial endpoint unavailable")
    assert len(metrics) == 1
    assert metrics[0].currency == "CNY"

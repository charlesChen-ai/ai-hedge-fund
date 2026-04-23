import pytest

from src.tools.market import (
    DataProvider,
    MarketProfile,
    get_backtest_dates,
    get_data_provider_for_ticker,
    get_default_benchmark,
    normalize_ticker,
    normalize_tickers,
)


def test_normalize_a_share_tickers():
    assert normalize_ticker("600519.SH").provider_symbol == "600519"
    assert normalize_ticker("600519.SH").exchange == "SH"
    assert normalize_ticker("000001").display_ticker == "000001.SZ"
    assert normalize_ticker("430047").display_ticker == "430047.BJ"


def test_normalize_us_ticker():
    ticker = normalize_ticker("aapl")
    assert ticker.display_ticker == "AAPL"
    assert ticker.provider_symbol == "AAPL"
    assert ticker.market_profile == MarketProfile.US


def test_mixed_market_tickers_are_rejected():
    with pytest.raises(ValueError, match="Mixed US and A-share"):
        normalize_tickers(["AAPL", "600519.SH"])


def test_auto_provider_routes_by_market(monkeypatch):
    monkeypatch.setenv("DATA_PROVIDER", "auto")
    assert get_data_provider_for_ticker("AAPL") == DataProvider.FINANCIAL_DATASETS
    assert get_data_provider_for_ticker("600519.SH") == DataProvider.AKSHARE


def test_benchmark_selection(monkeypatch):
    monkeypatch.setenv("A_SHARE_BENCHMARK", "000300.SH")
    assert get_default_benchmark(["AAPL"]) == "SPY"
    assert get_default_benchmark(["600519.SH"]) == "000300.SH"


def test_a_share_backtest_dates_use_china_calendar(monkeypatch):
    monkeypatch.setattr(
        "src.tools.market.get_a_share_trading_dates",
        lambda: {"2024-01-02", "2024-01-03", "2024-01-06"},
    )
    dates = get_backtest_dates("2024-01-01", "2024-01-05", ["600519.SH"])
    assert [date.strftime("%Y-%m-%d") for date in dates] == ["2024-01-02", "2024-01-03"]

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Iterable


class MarketProfile(str, Enum):
    US = "us"
    A_SHARE = "a_share"


class DataProvider(str, Enum):
    AUTO = "auto"
    FINANCIAL_DATASETS = "financialdatasets"
    AKSHARE = "akshare"


@dataclass(frozen=True)
class NormalizedTicker:
    display_ticker: str
    provider_symbol: str
    market_profile: MarketProfile
    exchange: str | None = None


_A_SHARE_PATTERN = re.compile(r"^(?P<code>\d{6})(?:\.(?P<exchange>SH|SZ|BJ))?$", re.IGNORECASE)
_US_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$", re.IGNORECASE)


def normalize_ticker(ticker: str) -> NormalizedTicker:
    raw = ticker.strip().upper()
    if not raw:
        raise ValueError("Ticker cannot be empty")

    a_share_match = _A_SHARE_PATTERN.match(raw)
    if a_share_match:
        code = a_share_match.group("code")
        exchange = (a_share_match.group("exchange") or _infer_a_share_exchange(code)).upper()
        if exchange not in {"SH", "SZ", "BJ"}:
            raise ValueError(f"Unsupported A-share exchange for ticker: {ticker}")
        return NormalizedTicker(
            display_ticker=f"{code}.{exchange}",
            provider_symbol=code,
            market_profile=MarketProfile.A_SHARE,
            exchange=exchange,
        )

    if _US_PATTERN.match(raw):
        return NormalizedTicker(
            display_ticker=raw,
            provider_symbol=raw,
            market_profile=MarketProfile.US,
            exchange=None,
        )

    raise ValueError(f"Unsupported ticker format: {ticker}")


def normalize_tickers(tickers: Iterable[str]) -> list[NormalizedTicker]:
    normalized = [normalize_ticker(ticker) for ticker in tickers]
    if not normalized:
        return []

    profiles = {ticker.market_profile for ticker in normalized}
    if len(profiles) > 1:
        raise ValueError("Mixed US and A-share tickers are not supported in the same run")
    return normalized


def get_market_profile_for_tickers(tickers: Iterable[str]) -> MarketProfile:
    normalized = normalize_tickers(tickers)
    if not normalized:
        return MarketProfile.US
    return normalized[0].market_profile


def get_market_profile_for_ticker(ticker: str) -> MarketProfile:
    return normalize_ticker(ticker).market_profile


def get_data_provider_for_ticker(ticker: str) -> DataProvider:
    configured = os.getenv("DATA_PROVIDER", DataProvider.AUTO.value).strip().lower()
    try:
        provider = DataProvider(configured)
    except ValueError as exc:
        raise ValueError(
            "DATA_PROVIDER must be one of: auto, financialdatasets, akshare"
        ) from exc

    if provider != DataProvider.AUTO:
        market_profile = get_market_profile_for_ticker(ticker)
        if provider == DataProvider.AKSHARE and market_profile != MarketProfile.A_SHARE:
            raise ValueError("DATA_PROVIDER=akshare only supports A-share tickers")
        if provider == DataProvider.FINANCIAL_DATASETS and market_profile != MarketProfile.US:
            raise ValueError("DATA_PROVIDER=financialdatasets only supports US tickers")
        return provider

    market_profile = get_market_profile_for_ticker(ticker)
    if market_profile == MarketProfile.A_SHARE:
        return DataProvider.AKSHARE
    return DataProvider.FINANCIAL_DATASETS


def is_a_share_ticker(ticker: str) -> bool:
    return get_market_profile_for_ticker(ticker) == MarketProfile.A_SHARE


def get_default_benchmark(tickers: Iterable[str]) -> str:
    market_profile = get_market_profile_for_tickers(tickers)
    if market_profile == MarketProfile.A_SHARE:
        return os.getenv("A_SHARE_BENCHMARK", "000300.SH").strip().upper()
    return "SPY"


@lru_cache(maxsize=1)
def get_a_share_trading_dates() -> set[str]:
    try:
        import akshare as ak

        df = ak.tool_trade_date_hist_sina()
    except Exception:
        return set()

    if df is None or df.empty:
        return set()

    date_column = "trade_date" if "trade_date" in df.columns else df.columns[0]
    dates = []
    for value in df[date_column].dropna().tolist():
        try:
            dates.append(str(value)[:10])
        except Exception:
            continue
    return set(dates)


def get_backtest_dates(start_date: str, end_date: str, tickers: Iterable[str]):
    import pandas as pd

    market_profile = get_market_profile_for_tickers(tickers)
    if market_profile != MarketProfile.A_SHARE:
        return pd.date_range(start_date, end_date, freq="B")

    calendar_dates = get_a_share_trading_dates()
    if calendar_dates:
        dates = [
            pd.Timestamp(date)
            for date in sorted(calendar_dates)
            if start_date <= date <= end_date
        ]
        return pd.DatetimeIndex(dates)

    return pd.date_range(start_date, end_date, freq="B")


def _infer_a_share_exchange(code: str) -> str:
    if code.startswith(("60", "68", "90")):
        return "SH"
    if code.startswith(("00", "30", "20")):
        return "SZ"
    if code.startswith(("43", "83", "87", "88")):
        return "BJ"
    raise ValueError(f"Cannot infer A-share exchange for ticker code: {code}")

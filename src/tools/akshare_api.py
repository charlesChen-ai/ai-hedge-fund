from __future__ import annotations

import logging
import os
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from io import StringIO
from typing import Any

import pandas as pd

from src.data.models import CompanyNews, FinancialMetrics, LineItem, Price
from src.tools.market import normalize_ticker

logger = logging.getLogger(__name__)


LINE_ITEM_FIELDS = {
    "book_value_per_share",
    "capital_expenditure",
    "cash_and_equivalents",
    "current_assets",
    "current_liabilities",
    "debt_to_equity",
    "depreciation_and_amortization",
    "dividends_and_other_cash_distributions",
    "earnings_per_share",
    "ebit",
    "ebitda",
    "free_cash_flow",
    "goodwill_and_intangible_assets",
    "gross_margin",
    "gross_profit",
    "interest_expense",
    "issuance_or_purchase_of_equity_shares",
    "net_income",
    "operating_expense",
    "operating_income",
    "operating_margin",
    "outstanding_shares",
    "research_and_development",
    "return_on_invested_capital",
    "revenue",
    "shareholders_equity",
    "total_assets",
    "total_debt",
    "total_liabilities",
    "working_capital",
}


def get_prices(ticker: str, start_date: str, end_date: str) -> list[Price]:
    normalized = normalize_ticker(ticker)
    try:
        import akshare as ak

        if _is_a_share_index(normalized.display_ticker):
            df = ak.index_zh_a_hist(
                symbol=normalized.provider_symbol,
                period="daily",
                start_date=_ak_date(start_date),
                end_date=_ak_date(end_date),
            )
        else:
            df = ak.stock_zh_a_hist(
                symbol=normalized.provider_symbol,
                period="daily",
                start_date=_ak_date(start_date),
                end_date=_ak_date(end_date),
                adjust=os.getenv("A_SHARE_PRICE_ADJUST", "qfq"),
            )
    except Exception as exc:
        logger.warning("Failed to fetch AKShare prices for %s: %s", ticker, exc)
        return []

    return _prices_from_df(df)


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[FinancialMetrics]:
    normalized = normalize_ticker(ticker)
    try:
        line_items = _load_a_share_line_items(normalized.provider_symbol, end_date, period, limit)
        market_cap = get_market_cap(ticker, end_date)
        valuation = _load_valuation(normalized.provider_symbol)
    except Exception as exc:
        logger.warning("Failed to fetch AKShare financial metrics for %s: %s", ticker, exc)
        line_items = []
        market_cap = None
        valuation = {}

    metrics: list[FinancialMetrics] = []
    for item in line_items[:limit]:
        metrics.append(_metric_from_line_item(ticker, item, market_cap, valuation))

    if not metrics:
        metrics.append(
            FinancialMetrics(
                ticker=normalized.display_ticker,
                report_period=end_date,
                period=period,
                currency="CNY",
                market_cap=market_cap,
                enterprise_value=None,
                price_to_earnings_ratio=valuation.get("price_to_earnings_ratio"),
                price_to_book_ratio=valuation.get("price_to_book_ratio"),
                price_to_sales_ratio=None,
                enterprise_value_to_ebitda_ratio=None,
                enterprise_value_to_revenue_ratio=None,
                free_cash_flow_yield=None,
                peg_ratio=None,
                gross_margin=None,
                operating_margin=None,
                net_margin=None,
                return_on_equity=None,
                return_on_assets=None,
                return_on_invested_capital=None,
                asset_turnover=None,
                inventory_turnover=None,
                receivables_turnover=None,
                days_sales_outstanding=None,
                operating_cycle=None,
                working_capital_turnover=None,
                current_ratio=None,
                quick_ratio=None,
                cash_ratio=None,
                operating_cash_flow_ratio=None,
                debt_to_equity=None,
                debt_to_assets=None,
                interest_coverage=None,
                revenue_growth=None,
                earnings_growth=None,
                book_value_growth=None,
                earnings_per_share_growth=None,
                free_cash_flow_growth=None,
                operating_income_growth=None,
                ebitda_growth=None,
                payout_ratio=None,
                earnings_per_share=None,
                book_value_per_share=None,
                free_cash_flow_per_share=None,
            )
        )
    return metrics[:limit]


def search_line_items(
    ticker: str,
    requested_line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[LineItem]:
    normalized = normalize_ticker(ticker)
    try:
        raw_items = _load_a_share_line_items(normalized.provider_symbol, end_date, period, limit)
    except Exception as exc:
        logger.warning("Failed to fetch AKShare line items for %s: %s", ticker, exc)
        raw_items = []

    requested = requested_line_items or sorted(LINE_ITEM_FIELDS)
    results: list[LineItem] = []
    for raw_item in raw_items[:limit]:
        payload = {
            "ticker": normalized.display_ticker,
            "report_period": raw_item.get("report_period") or end_date,
            "period": period,
            "currency": "CNY",
        }
        for field in requested:
            payload[field] = raw_item.get(field)
        results.append(LineItem(**payload))
    return results


def get_market_cap(ticker: str, end_date: str) -> float | None:
    normalized = normalize_ticker(ticker)
    try:
        import akshare as ak

        info_df = ak.stock_individual_info_em(symbol=normalized.provider_symbol)
        value = _extract_item_value(info_df, ["总市值", "总市值(元)"])
        if value is not None:
            return value
    except Exception as exc:
        logger.debug("AKShare individual info market cap unavailable for %s: %s", ticker, exc)

    valuation = _load_valuation(normalized.provider_symbol)
    return valuation.get("market_cap")


def get_company_news(ticker: str, end_date: str, start_date: str | None = None, limit: int = 1000) -> list[CompanyNews]:
    normalized = normalize_ticker(ticker)
    news_df = None
    try:
        import akshare as ak

        if hasattr(ak, "stock_news_em"):
            news_df = ak.stock_news_em(symbol=normalized.provider_symbol)
    except Exception as exc:
        logger.warning("Failed to fetch AKShare news for %s: %s", ticker, exc)
        return []

    if news_df is None or news_df.empty:
        return []

    news: list[CompanyNews] = []
    start_bound = start_date or "0000-00-00"
    end_bound = end_date
    for _, row in news_df.head(limit * 2).iterrows():
        title = _first_present(row, ["新闻标题", "标题", "title"])
        if not title:
            continue
        date_value = _first_present(row, ["发布时间", "时间", "日期", "date"])
        date_text = _normalize_date(str(date_value)) if date_value is not None else end_date
        if date_text < start_bound or date_text > end_bound:
            continue
        news.append(
            CompanyNews(
                ticker=normalized.display_ticker,
                title=str(title),
                author=None,
                source=str(_first_present(row, ["文章来源", "来源", "source"]) or "AKShare"),
                date=date_text,
                url=str(_first_present(row, ["新闻链接", "链接", "url"]) or ""),
            )
        )
        if len(news) >= limit:
            break
    return news


def get_insider_trades(*args, **kwargs):
    return []


def get_company_facts(ticker: str, end_date: str) -> dict[str, Any]:
    normalized = normalize_ticker(ticker)
    facts = {
        "ticker": normalized.display_ticker,
        "name": normalized.display_ticker,
        "industry": None,
        "sector": None,
        "exchange": normalized.exchange,
        "is_active": True,
        "listing_date": None,
        "location": "China",
        "market_cap": None,
    }
    try:
        import akshare as ak

        info_df = ak.stock_individual_info_em(symbol=normalized.provider_symbol)
        facts["name"] = str(_extract_item_raw_value(info_df, ["股票简称", "名称"]) or normalized.display_ticker)
        facts["industry"] = _extract_item_raw_value(info_df, ["行业"])
        facts["listing_date"] = _normalize_date(str(_extract_item_raw_value(info_df, ["上市时间"]) or "")) or None
        facts["market_cap"] = get_market_cap(ticker, end_date)
    except Exception:
        facts["market_cap"] = get_market_cap(ticker, end_date)
    return facts


def _load_a_share_line_items(symbol: str, end_date: str, period: str, limit: int) -> list[dict[str, Any]]:
    import akshare as ak

    statement_symbol = _statement_symbol(symbol)
    analysis_df = _safe_call(lambda: ak.stock_financial_analysis_indicator_em(symbol=symbol))
    balance_df = _safe_call(lambda: ak.stock_balance_sheet_by_report_em(symbol=statement_symbol))
    profit_df = _safe_call(lambda: ak.stock_profit_sheet_by_report_em(symbol=statement_symbol))
    cashflow_df = _safe_call(lambda: ak.stock_cash_flow_sheet_by_report_em(symbol=statement_symbol))

    report_periods = _collect_report_periods(end_date, limit, [analysis_df, balance_df, profit_df, cashflow_df])
    results = []
    for report_period in report_periods:
        analysis_row = _row_for_period(analysis_df, report_period)
        balance_row = _row_for_period(balance_df, report_period)
        profit_row = _row_for_period(profit_df, report_period)
        cashflow_row = _row_for_period(cashflow_df, report_period)
        results.append(_build_line_item(report_period, analysis_row, balance_row, profit_row, cashflow_row))
    return results


def _build_line_item(report_period: str, analysis_row, balance_row, profit_row, cashflow_row) -> dict[str, Any]:
    revenue = _row_value(profit_row, ["营业总收入", "营业收入", "主营业务收入", "TOTAL_OPERATE_INCOME", "OPERATE_INCOME"])
    net_income = _row_value(profit_row, ["净利润", "归属于母公司所有者的净利润", "PARENT_NETPROFIT", "NETPROFIT"])
    gross_profit = _row_value(profit_row, ["营业利润", "毛利润", "OPERATE_PROFIT"])
    operating_income = _row_value(profit_row, ["营业利润", "OPERATE_PROFIT"])
    total_assets = _row_value(balance_row, ["资产总计", "总资产", "TOTAL_ASSETS"])
    total_liabilities = _row_value(balance_row, ["负债合计", "总负债", "TOTAL_LIABILITIES"])
    current_assets = _row_value(balance_row, ["流动资产合计", "CURRENT_ASSETS", "CURRENT_ASSET_BALANCE"])
    current_liabilities = _row_value(balance_row, ["流动负债合计", "CURRENT_LIABILITIES", "CURRENT_LIAB_BALANCE"])
    equity = _row_value(balance_row, ["所有者权益(或股东权益)合计", "归属于母公司所有者权益合计", "股东权益合计", "TOTAL_PARENT_EQUITY", "TOTAL_EQUITY"])
    cash = _row_value(balance_row, ["货币资金", "MONETARYFUNDS"])
    total_debt = _sum_optional(
        _row_value(balance_row, ["短期借款", "SHORT_LOAN"]),
        _row_value(balance_row, ["长期借款", "LONG_LOAN"]),
        _row_value(balance_row, ["应付债券", "BOND_PAYABLE"]),
        _row_value(balance_row, ["一年内到期的非流动负债", "NONCURRENT_LIAB_1YEAR"]),
    )
    capex = _row_value(cashflow_row, ["购建固定资产、无形资产和其他长期资产支付的现金", "CONSTRUCT_LONG_ASSET"])
    operating_cash_flow = _row_value(cashflow_row, ["经营活动产生的现金流量净额", "NETCASH_OPERATE"])
    free_cash_flow = _subtract_optional(operating_cash_flow, capex)
    eps = _row_value(analysis_row, ["摊薄每股收益(元)", "基本每股收益", "每股收益"])
    if eps is None:
        eps = _row_value(profit_row, ["BASIC_EPS", "DILUTED_EPS"])
    bps = _row_value(analysis_row, ["每股净资产_调整后(元)", "每股净资产"])
    roe = _percentage_to_ratio(_row_value(analysis_row, ["净资产收益率(%)", "加权净资产收益率(%)"]))
    if roe is None:
        roe = _ratio_optional(net_income, equity)
    roa = _percentage_to_ratio(_row_value(analysis_row, ["总资产报酬率(%)", "总资产净利润率(%)"]))
    if roa is None:
        roa = _ratio_optional(net_income, total_assets)
    revenue_growth = _percentage_to_ratio(_row_value(analysis_row, ["主营业务收入增长率(%)", "营业收入增长率(%)"]))
    if revenue_growth is None:
        revenue_growth = _percentage_to_ratio(_row_value(profit_row, ["TOTAL_OPERATE_INCOME_YOY", "OPERATE_INCOME_YOY"]))
    earnings_growth = _percentage_to_ratio(_row_value(analysis_row, ["净利润增长率(%)", "归属净利润同比增长率(%)"]))
    if earnings_growth is None:
        earnings_growth = _percentage_to_ratio(_row_value(profit_row, ["PARENT_NETPROFIT_YOY", "NETPROFIT_YOY"]))
    gross_margin = _ratio_optional(gross_profit, revenue)
    operating_margin = _ratio_optional(operating_income, revenue)
    net_margin = _ratio_optional(net_income, revenue)
    debt_to_equity = _ratio_optional(total_debt, equity)
    working_capital = _subtract_optional(current_assets, current_liabilities)

    return {
        "report_period": report_period,
        "revenue": revenue,
        "net_income": net_income,
        "gross_profit": gross_profit,
        "operating_income": operating_income,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "current_assets": current_assets,
        "current_liabilities": current_liabilities,
        "shareholders_equity": equity,
        "cash_and_equivalents": cash,
        "total_debt": total_debt,
        "capital_expenditure": capex,
        "free_cash_flow": free_cash_flow,
        "earnings_per_share": eps,
        "book_value_per_share": bps,
        "return_on_invested_capital": roe,
        "debt_to_equity": debt_to_equity,
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
        "working_capital": working_capital,
        "ebit": operating_income,
        "ebitda": None,
        "operating_expense": _row_value(profit_row, ["销售费用", "SALE_EXPENSE"]),
        "interest_expense": _row_value(profit_row, ["利息费用", "财务费用", "INTEREST_EXPENSE", "FE_INTEREST_EXPENSE", "FINANCE_EXPENSE"]),
        "research_and_development": _row_value(profit_row, ["研发费用", "RESEARCH_EXPENSE", "ME_RESEARCH_EXPENSE"]),
        "depreciation_and_amortization": None,
        "goodwill_and_intangible_assets": _sum_optional(
            _row_value(balance_row, ["商誉", "GOODWILL"]),
            _row_value(balance_row, ["无形资产", "INTANGIBLE_ASSET"]),
        ),
        "dividends_and_other_cash_distributions": _row_value(cashflow_row, ["分配股利、利润或偿付利息支付的现金", "ASSIGN_DIVIDEND_PORFIT"]),
        "issuance_or_purchase_of_equity_shares": None,
        "outstanding_shares": None,
        "net_margin": net_margin,
        "return_on_equity": roe,
        "return_on_assets": roa,
        "revenue_growth": revenue_growth,
        "earnings_growth": earnings_growth,
    }


def _metric_from_line_item(ticker: str, item: dict[str, Any], market_cap: float | None, valuation: dict[str, float | None]) -> FinancialMetrics:
    normalized = normalize_ticker(ticker)
    total_debt = item.get("total_debt")
    total_assets = item.get("total_assets")
    operating_cash_flow = item.get("free_cash_flow")
    current_liabilities = item.get("current_liabilities")
    net_income = item.get("net_income")
    equity = item.get("shareholders_equity")
    fcf = item.get("free_cash_flow")
    revenue = item.get("revenue")

    return FinancialMetrics(
        ticker=normalized.display_ticker,
        report_period=item.get("report_period"),
        period="ttm",
        currency="CNY",
        market_cap=market_cap,
        enterprise_value=None,
        price_to_earnings_ratio=valuation.get("price_to_earnings_ratio"),
        price_to_book_ratio=valuation.get("price_to_book_ratio"),
        price_to_sales_ratio=_ratio_optional(market_cap, revenue),
        enterprise_value_to_ebitda_ratio=None,
        enterprise_value_to_revenue_ratio=None,
        free_cash_flow_yield=_ratio_optional(fcf, market_cap),
        peg_ratio=None,
        gross_margin=item.get("gross_margin"),
        operating_margin=item.get("operating_margin"),
        net_margin=item.get("net_margin"),
        return_on_equity=item.get("return_on_equity"),
        return_on_assets=item.get("return_on_assets"),
        return_on_invested_capital=item.get("return_on_invested_capital"),
        asset_turnover=_ratio_optional(revenue, total_assets),
        inventory_turnover=None,
        receivables_turnover=None,
        days_sales_outstanding=None,
        operating_cycle=None,
        working_capital_turnover=_ratio_optional(revenue, item.get("working_capital")),
        current_ratio=_ratio_optional(item.get("current_assets"), current_liabilities),
        quick_ratio=None,
        cash_ratio=_ratio_optional(item.get("cash_and_equivalents"), current_liabilities),
        operating_cash_flow_ratio=_ratio_optional(operating_cash_flow, current_liabilities),
        debt_to_equity=item.get("debt_to_equity"),
        debt_to_assets=_ratio_optional(total_debt, total_assets),
        interest_coverage=_ratio_optional(item.get("operating_income"), abs(item.get("interest_expense") or 0) or None),
        revenue_growth=item.get("revenue_growth"),
        earnings_growth=item.get("earnings_growth"),
        book_value_growth=None,
        earnings_per_share_growth=None,
        free_cash_flow_growth=None,
        operating_income_growth=None,
        ebitda_growth=None,
        payout_ratio=None,
        earnings_per_share=item.get("earnings_per_share"),
        book_value_per_share=item.get("book_value_per_share"),
        free_cash_flow_per_share=_ratio_optional(fcf, item.get("outstanding_shares")),
    )


def _load_valuation(symbol: str) -> dict[str, float | None]:
    valuation = {"market_cap": None, "price_to_earnings_ratio": None, "price_to_book_ratio": None}
    try:
        import akshare as ak

        if hasattr(ak, "stock_zh_valuation_baidu"):
            df = ak.stock_zh_valuation_baidu(symbol=symbol, indicator="总市值")
            if df is not None and not df.empty:
                valuation["market_cap"] = _coerce_float(df.iloc[-1].get("value") if "value" in df.columns else df.iloc[-1, -1])
    except Exception:
        pass
    return valuation


def _prices_from_df(df: pd.DataFrame | None) -> list[Price]:
    if df is None or df.empty:
        return []
    prices = []
    for _, row in df.iterrows():
        date_value = _first_present(row, ["日期", "date", "时间"])
        open_value = _first_present(row, ["开盘", "open"])
        close_value = _first_present(row, ["收盘", "close"])
        high_value = _first_present(row, ["最高", "high"])
        low_value = _first_present(row, ["最低", "low"])
        volume_value = _first_present(row, ["成交量", "volume"])
        if date_value is None or close_value is None:
            continue
        try:
            prices.append(
                Price(
                    open=float(open_value),
                    close=float(close_value),
                    high=float(high_value),
                    low=float(low_value),
                    volume=int(float(volume_value or 0)),
                    time=_normalize_date(str(date_value)),
                )
            )
        except Exception:
            continue
    return prices


def _safe_call(fn):
    try:
        buffer = StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            return fn()
    except Exception:
        return pd.DataFrame()


def _collect_report_periods(end_date: str, limit: int, dfs: list[pd.DataFrame]) -> list[str]:
    periods: list[str] = []
    for df in dfs:
        if df is None or df.empty:
            continue
        for _, row in df.iterrows():
            period = _row_period(row)
            if period and period <= end_date and period not in periods:
                periods.append(period)
    return sorted(periods, reverse=True)[:limit]


def _row_for_period(df: pd.DataFrame | None, report_period: str):
    if df is None or df.empty:
        return None
    for _, row in df.iterrows():
        if _row_period(row) == report_period:
            return row
    return None


def _row_period(row) -> str | None:
    value = _first_present(row, ["日期", "报告期", "REPORT_DATE", "报表日期"])
    if value is None:
        return None
    return _normalize_date(str(value))


def _row_value(row, names: list[str]) -> float | None:
    if row is None:
        return None
    return _coerce_float(_first_present(row, names))


def _first_present(row, names: list[str]):
    for name in names:
        try:
            value = row.get(name)
        except Exception:
            value = None
        if value is not None and not pd.isna(value):
            return value
    return None


def _extract_item_raw_value(df: pd.DataFrame | None, names: list[str]):
    if df is None or df.empty:
        return None
    item_col = "item" if "item" in df.columns else ("项目" if "项目" in df.columns else df.columns[0])
    value_col = "value" if "value" in df.columns else ("值" if "值" in df.columns else df.columns[-1])
    for _, row in df.iterrows():
        if str(row.get(item_col)) in names:
            return row.get(value_col)
    return None


def _extract_item_value(df: pd.DataFrame | None, names: list[str]) -> float | None:
    return _coerce_float(_extract_item_raw_value(df, names))


def _coerce_float(value) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    text = str(value).replace(",", "").replace("%", "").strip()
    if not text or text in {"-", "--", "None", "nan"}:
        return None
    multiplier = 1.0
    if text.endswith("亿"):
        multiplier = 100_000_000.0
        text = text[:-1]
    elif text.endswith("万"):
        multiplier = 10_000.0
        text = text[:-1]
    try:
        return float(text) * multiplier
    except Exception:
        return None


def _percentage_to_ratio(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 100.0


def _ratio_optional(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or abs(denominator) < 1e-12:
        return None
    return numerator / denominator


def _subtract_optional(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def _sum_optional(*values: float | None) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def _normalize_date(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return value[:10]


def _ak_date(value: str) -> str:
    return value.replace("-", "")


def _is_a_share_index(display_ticker: str) -> bool:
    return display_ticker in {"000300.SH", "000905.SH", "000016.SH"}


def _statement_symbol(symbol: str) -> str:
    normalized = normalize_ticker(symbol)
    return f"{normalized.exchange}{normalized.provider_symbol}"

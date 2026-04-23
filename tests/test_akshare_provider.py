import sys
from types import SimpleNamespace

import pandas as pd

from src.tools import api


def test_akshare_prices_are_normalized(monkeypatch):
    fake_ak = SimpleNamespace(
        stock_zh_a_hist=lambda **kwargs: pd.DataFrame(
            [
                {
                    "日期": "2024-01-02",
                    "开盘": 100.0,
                    "收盘": 101.0,
                    "最高": 102.0,
                    "最低": 99.0,
                    "成交量": 12345,
                }
            ]
        )
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_ak)

    prices = api.get_prices("600519.SH", "2024-01-01", "2024-01-03")

    assert len(prices) == 1
    assert prices[0].time == "2024-01-02"
    assert prices[0].close == 101.0
    assert prices[0].volume == 12345


def test_akshare_financials_and_line_items_are_normalized(monkeypatch):
    fake_ak = SimpleNamespace(
        stock_financial_analysis_indicator_em=lambda symbol: pd.DataFrame(
            [
                {
                    "日期": "2023-12-31",
                    "摊薄每股收益(元)": 5.0,
                    "每股净资产_调整后(元)": 30.0,
                    "净资产收益率(%)": 15.0,
                    "主营业务收入增长率(%)": 8.0,
                    "净利润增长率(%)": 10.0,
                }
            ]
        ),
        stock_balance_sheet_by_report_em=lambda symbol: pd.DataFrame(
            [
                {
                    "日期": "2023-12-31",
                    "资产总计": 1000.0,
                    "负债合计": 400.0,
                    "流动资产合计": 500.0,
                    "流动负债合计": 200.0,
                    "归属于母公司所有者权益合计": 600.0,
                    "货币资金": 120.0,
                    "短期借款": 50.0,
                    "长期借款": 100.0,
                }
            ]
        ),
        stock_profit_sheet_by_report_em=lambda symbol: pd.DataFrame(
            [
                {
                    "日期": "2023-12-31",
                    "营业总收入": 800.0,
                    "净利润": 160.0,
                    "营业利润": 200.0,
                    "销售费用": 50.0,
                    "财务费用": 10.0,
                    "研发费用": 30.0,
                }
            ]
        ),
        stock_cash_flow_sheet_by_report_em=lambda symbol: pd.DataFrame(
            [
                {
                    "日期": "2023-12-31",
                    "经营活动产生的现金流量净额": 180.0,
                    "购建固定资产、无形资产和其他长期资产支付的现金": 40.0,
                    "分配股利、利润或偿付利息支付的现金": 20.0,
                }
            ]
        ),
        stock_individual_info_em=lambda symbol: pd.DataFrame(
            [{"item": "总市值", "value": 5000.0}]
        ),
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_ak)

    metrics = api.get_financial_metrics("600519.SH", "2024-03-31", period="annual", limit=1)
    line_items = api.search_line_items(
        "600519.SH",
        ["revenue", "net_income", "free_cash_flow", "unsupported_field"],
        "2024-03-31",
        period="annual",
        limit=1,
    )

    assert len(metrics) == 1
    assert metrics[0].ticker == "600519.SH"
    assert metrics[0].currency == "CNY"
    assert metrics[0].market_cap == 5000.0
    assert metrics[0].earnings_per_share == 5.0
    assert metrics[0].return_on_equity == 0.15
    assert len(line_items) == 1
    assert line_items[0].revenue == 800.0
    assert line_items[0].net_income == 160.0
    assert line_items[0].free_cash_flow == 140.0
    assert line_items[0].unsupported_field is None


def test_akshare_news_falls_back_to_empty(monkeypatch):
    fake_ak = SimpleNamespace(stock_news_em=lambda symbol: pd.DataFrame())
    monkeypatch.setitem(sys.modules, "akshare", fake_ak)
    assert api.get_company_news("600519.SH", "2024-01-10", limit=5) == []

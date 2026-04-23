from src.backtesting.portfolio import Portfolio
from src.backtesting.trader import TradeExecutor


def test_a_share_buys_round_down_to_board_lots():
    portfolio = Portfolio(tickers=["600519.SH"], initial_cash=100_000.0, margin_requirement=0.0)

    executed = portfolio.apply_long_buy("600519.SH", 155, 100.0)

    assert executed == 100
    assert portfolio.get_snapshot()["positions"]["600519.SH"]["long"] == 100


def test_a_share_short_and_cover_are_disabled():
    portfolio = Portfolio(tickers=["600519.SH"], initial_cash=100_000.0, margin_requirement=0.5)
    executor = TradeExecutor()

    assert executor.execute_trade("600519.SH", "short", 100, 100.0, portfolio) == 0
    assert executor.execute_trade("600519.SH", "cover", 100, 100.0, portfolio) == 0
    assert portfolio.get_snapshot()["positions"]["600519.SH"]["short"] == 0


def test_a_share_sell_can_liquidate_odd_lot_remainder():
    portfolio = Portfolio(tickers=["600519.SH"], initial_cash=100_000.0, margin_requirement=0.0)
    portfolio.apply_long_buy("600519.SH", 155, 100.0)
    portfolio.apply_long_buy("600519.SH", 100, 100.0)

    # Simulate an odd-lot remainder from corporate action/imported state.
    portfolio._portfolio["positions"]["600519.SH"]["long"] = 105

    executed = portfolio.apply_long_sell("600519.SH", 105, 100.0)

    assert executed == 105
    assert portfolio.get_snapshot()["positions"]["600519.SH"]["long"] == 0

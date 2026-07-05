"""백테스트 엔진 — 월간 rebalance 포트폴리오 시뮬레이션 + 성과 지표.

전략은 '교체 가능 모듈' (backtest.strategies.Strategy 인터페이스).
엔진은 체결·수수료·포트폴리오·성과만 담당. look-ahead 금지: rebalance일 종가 기준.
전략 스펙: ~/projects/autotrader/strategy-spec-v1.md
"""
import numpy as np
import pandas as pd


def month_first_business_days(index):
    """각 월의 첫 영업일(rebalance일) 타임스탬프 리스트."""
    seen, out = set(), []
    for d in index:
        ym = (d.year, d.month)
        if ym not in seen:
            seen.add(ym)
            out.append(d)
    return out


def sma(s, window):
    return s.rolling(window).mean()


def momentum(s, window):
    return s.pct_change(window)


class Portfolio:
    def __init__(self, cash, fee):
        self.cash = cash
        self.holdings = {}        # symbol -> qty
        self.avg_cost = {}        # symbol -> 평균단가
        self.fee = fee
        self.trades = []

    def buy_amount(self, symbol, amount, price, date, reason=""):
        """현금 'amount' 어치 매수. 현금 한도 내에서."""
        if amount <= 0 or price <= 0 or np.isnan(price):
            return
        amount = min(amount, self.cash)
        if amount <= 0:
            return
        qty = amount / (price * (1 + self.fee))
        old_qty = self.holdings.get(symbol, 0.0)
        old_cost = self.avg_cost.get(symbol, 0.0)
        new_qty = old_qty + qty
        self.avg_cost[symbol] = (old_cost * old_qty + price * qty) / new_qty
        self.holdings[symbol] = new_qty
        self.cash -= qty * price * (1 + self.fee)
        self.trades.append((date, symbol, "BUY", qty, price, reason))

    def sell_qty(self, symbol, qty, price, date, reason=""):
        held = self.holdings.get(symbol, 0.0)
        qty = min(qty, held)
        if qty <= 0 or price <= 0 or np.isnan(price):
            return
        self.cash += qty * price * (1 - self.fee)
        self.holdings[symbol] = held - qty
        if self.holdings[symbol] <= 1e-9:
            self.holdings[symbol] = 0.0
            self.avg_cost[symbol] = 0.0
        self.trades.append((date, symbol, "SELL", qty, price, reason))

    def value(self, price_row):
        v = self.cash
        for sym, qty in self.holdings.items():
            if qty > 0 and sym in price_row and not np.isnan(price_row[sym]):
                v += qty * price_row[sym]
        return v


def _indicators(prices):
    """심볼별 지표(sma200, mom252)를 미리 계산."""
    out = {}
    for sym in prices.columns:
        s = prices[sym]
        out[sym] = {"sma200": sma(s, 200), "mom252": momentum(s, 252)}
    return out


def run_backtest(strategy, prices, initial_cash=10_000, fee=0.001):
    """전략을 prices 위에서 월간 rebalance 실행 -> (일일 포트폴리오 가치 Series, 거래내역)."""
    ind = _indicators(prices)
    port = Portfolio(initial_cash, fee)
    rebal_set = set(month_first_business_days(prices.index))

    values = []
    for date, row in prices.iterrows():
        if date in rebal_set:
            market = {}
            for sym in prices.columns:
                market[sym] = {
                    "close": row[sym],
                    "sma200": ind[sym]["sma200"].loc[date],
                    "mom252": ind[sym]["mom252"].loc[date],
                }
            state = {
                "cash": port.cash,
                "holdings": dict(port.holdings),
                "avg_cost": dict(port.avg_cost),
            }
            for o in strategy.on_rebalance(date, market, state):
                sym, side = o["symbol"], o["side"]
                price = row[sym]
                reason = o.get("reason", "")
                if side == "BUY":
                    port.buy_amount(sym, o.get("amount", 0), price, date, reason)
                elif side == "SELL":
                    held = port.holdings.get(sym, 0.0)
                    qty = o.get("qty", held * o.get("fraction", 1.0))
                    port.sell_qty(sym, qty, price, date, reason)
        values.append(port.value(row))

    pv = pd.Series(values, index=prices.index, name="value")
    return pv, port.trades


def metrics(pv, initial_cash):
    """핵심 성과 지표. 총수익률/CAGR/Sharpe/MDD."""
    ret = pv.pct_change().dropna()
    years = max((pv.index[-1] - pv.index[0]).days / 365.25, 1e-9)
    final = pv.iloc[-1]
    total_return = final / initial_cash - 1
    cagr = (final / initial_cash) ** (1 / years) - 1
    sharpe = (ret.mean() / ret.std() * np.sqrt(252)) if ret.std() > 0 else 0.0
    mdd = ((pv / pv.cummax()) - 1).min()
    return {
        "final": final,
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "mdd": mdd,
    }

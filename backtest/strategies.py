"""전략 모듈(pluggable) — 동일 인터페이스, 교체 가능.

인터페이스:
    on_rebalance(date, market, state) -> list[order]
        market[sym] = {close, sma200, mom252}
        state = {cash, holdings, avg_cost}
        order  = {symbol, side: BUY|SELL, amount|qty|fraction, reason}

target 심볼 일반화(기본 QQQ). 하이브리드는 benchmark(기본 SHV)로 레짔 판정.
전략 스펙: ~/projects/autotrader/strategy-spec-v1.md
"""
import numpy as np


class Strategy:
    def __init__(self, params, target="QQQ", benchmark="SHV"):
        self.params = params
        self.target = target
        self.benchmark = benchmark

    def on_rebalance(self, date, market, state):
        raise NotImplementedError


def _down_budget(base, k, cap, price, sma200):
    """라오어식 하락 가산 예산: sma200 대비 하락할수록 증량, cap로 상한."""
    if sma200 is None or np.isnan(sma200) or sma200 <= 0:
        return base
    d = (sma200 - price) / sma200            # 양수 = 하락폭
    return min(base * (1 + k * max(0.0, d)), base * cap)


class HybridStrategy(Strategy):
    """라오어 분할매수 + VAA/DAA식 레짔 필터.
    BULL(target 모멘텀 > benchmark) → 분할매수. BEAR → 보유 비중(exit_ratio) 현금 대피."""

    def on_rebalance(self, date, market, state):
        p = self.params
        tgt = market[self.target]
        bench = market[self.benchmark]
        m_q, m_s = tgt["mom252"], bench["mom252"]
        price, sma200 = tgt["close"], tgt["sma200"]
        orders = []

        bull = (not np.isnan(m_q)) and (not np.isnan(m_s)) and (m_q > m_s)
        if bull:
            budget = _down_budget(p["base"], p["k"], p["cap"], price, sma200)
            orders.append({"symbol": self.target, "side": "BUY", "amount": budget,
                           "reason": f"DCA bull m={m_q:.2%}"})
        else:
            held = state["holdings"].get(self.target, 0.0)
            if held > 0:
                orders.append({"symbol": self.target, "side": "SELL",
                               "qty": held * p["exit_ratio"],
                               "reason": f"regime bear m={m_q:.2%}->cash"})
        return orders


class DCAStrategy(Strategy):
    """순수 분할매수 — 레짔 필터 없이 매월 하락 가산 매수(하이브리드와 비교용)."""

    def on_rebalance(self, date, market, state):
        p = self.params
        tgt = market[self.target]
        budget = _down_budget(p["base"], p["k"], p["cap"], tgt["close"], tgt["sma200"])
        return [{"symbol": self.target, "side": "BUY", "amount": budget, "reason": "DCA no-filter"}]


class BuyHoldStrategy(Strategy):
    """첫 rebalance에 전액 target 매수 후 보유(엔진 정합성·벤치마크 검증용)."""

    def __init__(self, params, target="QQQ", benchmark="SHV"):
        super().__init__(params, target, benchmark)
        self._invested = False

    def on_rebalance(self, date, market, state):
        if not self._invested and state["cash"] > 0:
            self._invested = True
            return [{"symbol": self.target, "side": "BUY", "amount": state["cash"], "reason": "B&H init"}]
        return []

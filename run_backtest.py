"""단일 종목 백테스트 실행 진입점.

하이브리드(라오어 뼈대 + 레짔 필터) vs 순수 DCA vs Buy&Hold QQQ 비교.
첫 백테스트 — 전략 스펙 §7. 결과를 숫자로 이사님께 보고.

실행:
    /home/ubuntu/.venvs/autotrader/bin/python run_backtest.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest.data import load_prices
from backtest.engine import run_backtest, metrics
from backtest.strategies import HybridStrategy, DCAStrategy, BuyHoldStrategy

INITIAL_CASH = 10_000      # USD
SPLITS = 60                # 분할 수(5년 분량)
BASE = INITIAL_CASH / SPLITS
FEE = 0.001                # 왕복 0.1%

PARAMS = {"base": BASE, "k": 2.0, "cap": 3.0, "exit_ratio": 1.0}


def main():
    prices = load_prices(["QQQ", "SHV"], start="2010-01-01", end="2026-06-26")
    print(f"데이터: {prices.shape}  {prices.index.min().date()} -> {prices.index.max().date()}")
    print(f"자본 ${INITIAL_CASH:,} / 분할 {SPLITS} (1회 기본 ${BASE:.2f}) / 수수료 {FEE*100:.2f}%\n")

    strategies = {
        "Buy&Hold QQQ": BuyHoldStrategy(PARAMS),
        "순수 DCA": DCAStrategy(PARAMS),
        "하이브리드(★)": HybridStrategy(PARAMS),
    }

    results = {}
    for name, strat in strategies.items():
        pv, trades = run_backtest(strat, prices, INITIAL_CASH, fee=FEE)
        m = metrics(pv, INITIAL_CASH)
        m["n_trades"] = len(trades)
        m["n_buys"] = sum(1 for t in trades if t[2] == "BUY")
        m["n_sells"] = sum(1 for t in trades if t[2] == "SELL")
        results[name] = (m, trades)

    # 성과 표
    hdr = f"{'전략':<16}{'최종($)':>10}{'총수익률':>11}{'CAGR':>9}{'Sharpe':>8}{'MDD':>9}{'매수':>5}{'매도':>5}"
    print(hdr)
    print("-" * len(hdr))
    for name, (m, _) in results.items():
        print(f"{name:<16}{m['final']:>10,.0f}{m['total_return']*100:>10.1f}%"
              f"{m['cagr']*100:>8.1f}%{m['sharpe']:>8.2f}{m['mdd']*100:>8.1f}%"
              f"{m['n_buys']:>5}{m['n_sells']:>5}")

    # 하이브리드 현금대피(매도) 일자 샘플
    hybrid_trades = results["하이브리드(★)"][1]
    sells = [t for t in hybrid_trades if t[2] == "SELL"]
    print(f"\n[하이브리드] 레짔 전환(현금대피) 횟수: {len(sells)}")
    for t in sells[:8]:
        print(f"  {t[0].date()}  SELL {t[3]:.2f}주 @ ${t[4]:.2f}  ({t[5]})")
    if len(sells) > 8:
        print(f"  ... 외 {len(sells)-8}건")


if __name__ == "__main__":
    main()

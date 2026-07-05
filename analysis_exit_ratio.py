"""야간 리서치 — exit=0 우위의 원인 / 기간 / 심볼 견고성 (매니저 지시 07-02).

벤치마크 = 현금(0% 수익). SHV가 2007년 시작이라 2000-26(닷컴·2008) 커버 불가하여 단순화.
레짔 정의: 대상 12개월 모멘텀 > 0 이면 BULL.
splits=60 고정(이전 세팅과 일관).

출력:
  - 원인 분석: exit=1.0 의 BEAR 매도 후 12개월 성과 → 오판률(매도가 손해였는지)
  - 기간×심볼 견고성: QQQ/SPY × {2000-26, 2010-26, 2020-26} × exit_ratio
"""
import sys
sys.path.insert(0, "/home/ubuntu/projects/autotrader")

import numpy as np
from backtest.data import load_prices
from backtest.engine import run_backtest, metrics
from backtest.strategies import HybridStrategy

INITIAL = 10_000
SPLITS = 60
BASE = INITIAL / SPLITS
PARAMS = {"base": BASE, "k": 2.0, "cap": 3.0}
RATIOS = [0, 0.3, 0.5, 0.7, 1.0]
BENCH = "CASH"   # 현금(0% 수익) 벤치마크

PERIODS = [
    ("2000-01-01", "2026-06-26", "2000-26"),
    ("2010-01-01", "2026-06-26", "2010-26"),
    ("2020-01-01", "2026-06-26", "2020-26"),
]


def load_with_cash(target, start, end):
    p = load_prices([target], start=start, end=end)
    p[BENCH] = 1.0           # 현금 가격 상수 → 모멘텀 0
    return p


def cause_analysis(target, start, end, label):
    """exit=1.0 전략의 BEAR 매도 이후 ~12개월 대상 성과 → 오판률."""
    prices = load_with_cash(target, start, end)
    p = dict(PARAMS); p["exit_ratio"] = 1.0
    strat = HybridStrategy(p, target=target, benchmark=BENCH)
    pv, trades = run_backtest(strat, prices, INITIAL, fee=0.001)
    sells = [t for t in trades if t[2] == "SELL"]
    closes = prices[target]
    print(f"\n### 원인 분석: {target} {label} (exit=1.0) — BEAR 매도 후 12m")
    print(f"BEAR 매도 횟수: {len(sells)}")
    rows = []
    for t in sells:
        d = t[0]; sp = t[4]
        future = closes.loc[d:].iloc[1:253]
        if len(future) < 12:
            continue
        ret = future.iloc[-1] / sp - 1
        rows.append((d.strftime("%Y-%m"), sp, future.iloc[-1], ret))
    if not rows:
        print("  매도 후 12m 데이터 부족")
        return
    avg = float(np.mean([r[3] for r in rows]))
    pos = sum(1 for r in rows if r[3] > 0)
    print(f"{'매도월':<9}{'매도가':>9}{'12m후':>9}{'12m수익':>9}")
    for m in rows:
        print(f"{m[0]:<9}{m[1]:>9.1f}{m[2]:>9.1f}{m[3]*100:>8.1f}%")
    print(f"→ 평균 12m 수익 {avg*100:.1f}% | 오판(양수=매도가 손해) {pos}/{len(rows)} = {pos/len(rows)*100:.0f}%")


def run_grid(target):
    print(f"\n### 견고성: {target} — exit_ratio × 기간 (벤치마크=현금)")
    print(f"{'기간':<9}{'exit':>6}{'수익률':>10}{'CAGR':>8}{'MDD':>9}{'Sharpe':>8}{'매도':>5}")
    for start, end, label in PERIODS:
        prices = load_with_cash(target, start, end)
        for er in RATIOS:
            p = dict(PARAMS); p["exit_ratio"] = er
            strat = HybridStrategy(p, target=target, benchmark=BENCH)
            pv, trades = run_backtest(strat, prices, INITIAL, fee=0.001)
            m = metrics(pv, INITIAL)
            nsell = sum(1 for t in trades if t[2] == "SELL")
            print(f"{label:<9}{er:>6.1f}{m['total_return']*100:>9.1f}%"
                  f"{m['cagr']*100:>7.1f}%{m['mdd']*100:>8.1f}%{m['sharpe']:>8.2f}{nsell:>5}")


if __name__ == "__main__":
    print(f"자본 ${INITIAL:,} / 분할 {SPLITS} / 벤치마크={BENCH}(0% 수익) / 수수료 0.1%")
    cause_analysis("QQQ", "2010-01-01", "2026-06-26", "2010-26")
    cause_analysis("QQQ", "2000-01-01", "2026-06-26", "2000-26")
    run_grid("QQQ")
    run_grid("SPY")
    print("\n완료.")

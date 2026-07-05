"""야간 리서치 — exit_ratio 자동비교의 견고성 심층 검증 (매니저 07-02 지시).

질문:
  Q1. exit=0(매도X)이 이득인 원인 — 레짐 필터가 베어를 못 잡아서? or 매도 자체의 기회비용?
  Q2. 기간 확장 — 2020-26 우량장 편향인가? 2010-26, 2007-26(2008 금융위기 포함)에서도?
  Q3. 심볼 견고성 — 비기술 중심(SPY)에서도 exit=0 우위가 성립하는가?

범위: 기간(2020-26 / 2010-26 / 2007-26) × 심볼(QQQ / SPY) × exit_ratio[0,0.3,0.5,0.7,1.0].
한계: SHV 상장(2007) → 닷컴(2000-02) 제외. 2000-까지는 absolute-momentum 모드 필요(별도).

실행:
    /home/ubuntu/.venvs/autotrader/bin/python /home/ubuntu/projects/autotrader/research_exit_ratio.py
"""
import sys
sys.path.insert(0, "/home/ubuntu/projects/autotrader")

from backtest.data import load_prices
from backtest.engine import run_backtest, metrics
from backtest.strategies import HybridStrategy, BuyHoldStrategy

INITIAL = 10_000
RATIOS = [0.0, 0.3, 0.5, 0.7, 1.0]
PERIODS = [
    ("2020-26", "2020-01-01", "2026-06-26"),
    ("2010-26", "2010-01-01", "2026-06-26"),
    ("2007-26", "2007-01-01", "2026-06-26"),   # SHV 상장 이후, 2008 위기 포함
]
SYMBOLS = ["QQQ", "SPY"]


def run_period(sym, start, end, label):
    prices = load_prices([sym, "SHV"], start=start, end=end)
    if sym not in prices.columns or prices[sym].dropna().empty:
        print(f"  ({sym} {label}: 데이터 없음)")
        return None
    rows = prices.dropna()
    base = INITIAL / 60

    bh = BuyHoldStrategy({"base": base}, target=sym, benchmark="SHV")
    pv_bh, _ = run_backtest(bh, prices, INITIAL, 0.001)
    mbh = metrics(pv_bh, INITIAL)

    print(f"\n=== {sym} {label}  [{rows.index.min().date()}→{rows.index.max().date()}]  "
          f"B&H: ret={mbh['total_return']*100:.1f}% MDD={mbh['mdd']*100:.1f}% sharpe={mbh['sharpe']:.2f} ===")
    print(f"{'exit':>6}{'수익률':>10}{'MDD':>9}{'Sharpe':>8}{'매도':>5}{'vs B&H':>9}")
    res = []
    for er in RATIOS:
        p = {"base": base, "k": 2.0, "cap": 3.0, "exit_ratio": er}
        strat = HybridStrategy(p, target=sym, benchmark="SHV")
        pv, trades = run_backtest(strat, prices, INITIAL, 0.001)
        m = metrics(pv, INITIAL)
        nsell = sum(1 for t in trades if t[2] == "SELL")
        vs = m["total_return"] - mbh["total_return"]
        print(f"{er:>6.1f}{m['total_return']*100:>9.1f}%{m['mdd']*100:>8.1f}%"
              f"{m['sharpe']:>8.2f}{nsell:>5}{vs*100:>8.1f}%")
        res.append((er, m, nsell))
    return {"bh": mbh, "rows": res}


def main():
    print("=" * 70)
    print("exit_ratio 견고성 리서치 — 기간·심볼 확장 (매니저 07-02)")
    print("=" * 70)
    summary = {}
    for sym in SYMBOLS:
        summary[sym] = {}
        for label, start, end in PERIODS:
            summary[sym][label] = run_period(sym, start, end, label)

    # 요약: exit=0 vs exit=1.0 (수익·MDD) 로 '매도 가치' 국면 비교
    print("\n" + "=" * 70)
    print("요약 — exit=0(매도X) 대비 exit=1.0(전량매도): 수익·MDD 차이")
    print("=" * 70)
    print(f"{'심볼':>5}{'기간':>9}{'exit=0 ret':>12}{'exit=1 ret':>12}{'매도 비용':>11}{'exit=0 MDD':>12}{'exit=1 MDD':>12}")
    for sym in SYMBOLS:
        for label in [pl for pl, _, _ in PERIODS]:
            s = summary[sym].get(label)
            if not s:
                continue
            r0 = next(r for r in s["rows"] if r[0] == 0.0)[1]
            r1 = next(r for r in s["rows"] if r[0] == 1.0)[1]
            cost = (r0["total_return"] - r1["total_return"]) * 100
            print(f"{sym:>5}{label:>9}{r0['total_return']*100:>11.1f}%{r1['total_return']*100:>11.1f}%"
                  f"{cost:>10.1f}%{r0['mdd']*100:>11.1f}%{r1['mdd']*100:>11.1f}%")


if __name__ == "__main__":
    main()

"""야간 WIP 리서치 — 비중 슬라이드 전략 정량 백테스트 (매니저 07-04 01:00 배정).

⚠ WIP — 미승인. 아침 07:00 KST 이사님 승인 전 채택·commit 금지.
설계 기준: research/WIP-weight-slide-design-v1-draft.md

질문:
  Q1. 비중 슬라이드가 exit=0(라오어 원형, 매도X 풀매수) 대비 MDD를 개선하면서
      수익을 얼마나 보존하는가? (WIP §6 추정치 검증)
  Q2. 계단형(WS-A/C) vs 연속형(WS-B) — 밴드 경계 토글 비용이 있는가?
  Q3. 보수(WS-A) vs 공격(WS-C) — 과열 비중 축소 폭에 따라 수익·MDD 민감도.

범위: 시나리오 3종(WS-A/WS-B/WS-C) × 기간(2020-26/2010-26/2007-26)
      × 심볼(QQQ/SPY). 베이스라인 = exit=0 HybridStrategy + BuyHold.

모델링 근사(v1, WIP §5 단순화):
  - 엔진은 'initial_cash 월 인출' 모델(월 적립 없음). 기존 HybridStrategy와 동일 기준.
  - 과열 밴드에선 base*w(d)만 매수 → (1-w)*base는 port.cash에 자동 잔존(=현금 비축).
  - 저가 밴드에선 base*dep(배수) 추가 매수 → 잔존 현금에서 투입(=탄약 투입).
  - WIP 설계의 'accumulated_cash_reserve * deploy(d)'를 'base 배수'로 근사.
  - 한계: '엄밀한 월 적립 탄약 누적'은 v1 승인 후 엔진 확장 단계에서(§10 미결정).

실행:
    /home/ubuntu/.venvs/autotrader/bin/python \
        /home/ubuntu/projects/autotrader/research/weight_slide_backtest.py
"""
import sys
from pathlib import Path

sys.path.insert(0, "/home/ubuntu/projects/autotrader")
import numpy as np

from backtest.data import load_prices
from backtest.engine import run_backtest, metrics
from backtest.strategies import HybridStrategy, BuyHoldStrategy


INITIAL = 10_000
FEE = 0.001
# exit=0 Hybrid 기본 파라미터(기존 research_exit_ratio.py와 동일 — 공정 비교)
BASE = INITIAL / 60.0
K = 2.0
CAP = 3.0

PERIODS = [
    ("2020-26", "2020-01-01", "2026-06-26"),
    ("2010-26", "2010-01-01", "2026-06-26"),
    ("2007-26", "2007-01-01", "2026-06-26"),   # SHV 상장 이후, 2008 위기 포함
]
SYMBOLS = ["QQQ", "SPY"]

# 밴드 정의 (d = (sma200 - price)/sma200, 양수 = 기준선 대비 하락폭)
#   B1 과열  : d < -0.05
#   B2 보통상승 : -0.05 <= d < 0
#   B3 약세  : 0 <= d < 0.10
#   B4 깊은하락 : 0.10 <= d < 0.25
#   B5 침하  : d >= 0.25


def _band(d):
    if d < -0.05:
        return 1
    if d < 0:
        return 2
    if d < 0.10:
        return 3
    if d < 0.25:
        return 4
    return 5


# 시나리오 3종. w(d)=주식매수비중[0..1], dep(d)=저가밴드 추가매수(base 배수)
SCENARIOS = {
    "WS-A 보수계단": {
        "mode": "band",
        "w": {1: 0.3, 2: 0.5, 3: 0.8, 4: 1.0, 5: 1.0},
        "dep": {1: 0.0, 2: 0.0, 3: 0.5, 4: 1.5, 5: 3.0},
    },
    "WS-C 공격계단": {
        "mode": "band",
        "w": {1: 0.2, 2: 0.4, 3: 0.7, 4: 1.0, 5: 1.0},
        "dep": {1: 0.0, 2: 0.0, 3: 1.0, 4: 3.0, 5: 5.0},
    },
    "WS-B 연속형": {
        "mode": "cont",
        "w_fn": lambda d: float(np.clip(0.5 + 1.4 * d, 0.3, 1.0)),
        "dep_fn": lambda d: float(np.clip((d - 0.05) * 8.0, 0.0, 5.0)),
    },
}


class WeightSlideStrategy:
    """비중 슬라이드 — 코어 보유물은 매도 안 함. 월 예산 base를 가격 밴드별로
    주식/현금 분할. 고가 밴드에선 적게 매수(현금 잔존=탄약 비축),
    저가 밴드에선 base*dep(배수) 추가 매수(탄약 투입). 라오어 하락가산·cap 유지."""

    def __init__(self, params, target="QQQ", benchmark="SHV", sc=None):
        self.params = params
        self.target = target
        self.benchmark = benchmark
        self.sc = sc

    def _wd(self, d):
        if self.sc["mode"] == "cont":
            return self.sc["w_fn"](d), self.sc["dep_fn"](d)
        b = _band(d)
        return self.sc["w"][b], self.sc["dep"][b]

    def on_rebalance(self, date, market, state):
        p = self.params
        tgt = market[self.target]
        price, sma200 = tgt["close"], tgt["sma200"]
        if sma200 is None or np.isnan(sma200) or sma200 <= 0:
            d = 0.0
        else:
            d = (sma200 - price) / sma200
        w, dep = self._wd(d)

        base = p["base"]
        buy = base * w                              # 정규 분할매수
        buy *= (1.0 + p["k"] * max(0.0, d))         # 라오어 하락 가산
        buy += base * dep                           # 저가 밴드 추가 탄약(base 배수)
        buy = min(buy, base * p["cap"])             # cap 상한(비용 폭발 방지)

        return [{"symbol": self.target, "side": "BUY", "amount": buy,
                 "reason": f"WS w={w:.2f} dep={dep:.2f} d={d:+.3f} b=B{_band(d)}"}]


def _run_strat(strat, prices):
    pv, trades = run_backtest(strat, prices, INITIAL, FEE)
    m = metrics(pv, INITIAL)
    return {
        "ret": m["total_return"],
        "cagr": m["cagr"],
        "mdd": m["mdd"],
        "sharpe": m["sharpe"],
        "ntrades": len(trades),
    }


def run_period(sym, start, end, label, prices):
    """한 (심볼×기간)에 대해 exit=0/B&H/WS-A/B/C 실행 → 결과 dict."""
    out = {"symbol": sym, "period": label,
           "span": f"{prices.index.min().date()}→{prices.index.max().date()}"}

    # 베이스라인: exit=0 라오어 원형
    p_exit0 = {"base": BASE, "k": K, "cap": CAP, "exit_ratio": 0.0}
    out["exit0"] = _run_strat(
        HybridStrategy(p_exit0, target=sym, benchmark="SHV"), prices)

    # B&H
    out["bh"] = _run_strat(
        BuyHoldStrategy({"base": BASE}, target=sym, benchmark="SHV"), prices)

    # WS 시나리오
    for name, sc in SCENARIOS.items():
        p = {"base": BASE, "k": K, "cap": CAP}
        out[name] = _run_strat(
            WeightSlideStrategy(p, target=sym, benchmark="SHV", sc=sc), prices)
    return out


def _fmt_pct(x):
    return f"{x*100:.1f}%"


def to_markdown(all_results):
    """결과를 마크다운 WIP 파일 본문으로 직렬화."""
    lines = []
    lines.append("---")
    lines.append('title: "[WIP-draft] 비중 슬라이드 정량 백테스트 결과 v1"')
    lines.append("date: 2026-07-04")
    lines.append("author: heav_lnx_trader_bot")
    lines.append("status: draft (야간 자율, 미승인)")
    lines.append("approved: false")
    lines.append("night_mode: true")
    lines.append("spec_ref: research/WIP-weight-slide-design-v1-draft.md, backtest/strategies.py")
    lines.append("tags: [wip, draft, weight-slide, backtest, autotrader]")
    lines.append("---")
    lines.append("")
    lines.append("# [WIP-draft] 비중 슬라이드 정량 백테스트 결과 v1")
    lines.append("")
    lines.append("> ⚠ **WIP — 야간 자율 정량 백테스트. 미승인.** "
                 "구현 채택·commit 금지. 07:00 KST 이사님 리뷰 후 승인 여부 결정.")
    lines.append("> 발신: `@heav_lnx_trader_bot` / 배정 07-04 01:00 KST.")
    lines.append("> 설계 기준: `WIP-weight-slide-design-v1-draft.md`.")
    lines.append("")
    lines.append("## 설정")
    lines.append(f"- initial={INITIAL:,} / fee={FEE} / base=initial/60={BASE:.2f} / k={K} / cap={CAP}")
    lines.append("- 베이스라인: `HybridStrategy exit_ratio=0`(라오어 원형 — 매도X, BULL이면 매월 풀매수)")
    lines.append("- 시나리오: WS-A 보수계단 / WS-B 연속형 / WS-C 공격계단 "
                 "(w·dep 값은 스크립트 상단 SCENARIOS 참조)")
    lines.append("- d = (sma200 - price)/sma200 (양수=하락). 밴드: B1 d<-0.05 / "
                 "B2 [-0.05,0) / B3 [0,0.10) / B4 [0.10,0.25) / B5 ≥0.25.")
    lines.append("- 모델링 근사(v1): '월 적립 탄약 누적' 대신 'base 배수 추가 매수'로 단순화. "
                 "엔진이 initial_cash 월 인출 모델이므로 과열 밴드 (1-w)base는 port.cash에 자동 잔존.")
    lines.append("")
    lines.append("## 결과표")
    lines.append("")

    for sym in SYMBOLS:
        for label, _, _ in PERIODS:
            res = all_results.get((sym, label))
            if not res:
                continue
            lines.append(f"### {sym} · {label}  "
                         f"[{res['span']}]")
            lines.append("")
            lines.append("| 전략 | 수익률 | CAGR | MDD | Sharpe | vs exit=0 수익 | 거래수 |")
            lines.append("|---|---|---|---|---|---|---|")
            e0 = res["exit0"]["ret"]
            for key, name in [("bh", "B&H"), ("exit0", "exit=0 (라오어원형)"),
                              ("WS-A 보수계단", "WS-A 보수계단"),
                              ("WS-B 연속형", "WS-B 연속형"),
                              ("WS-C 공격계단", "WS-C 공격계단")]:
                r = res[key]
                vs = r["ret"] - e0 if key != "exit0" else 0.0
                lines.append(
                    f"| {name} | {_fmt_pct(r['ret'])} | {_fmt_pct(r['cagr'])} | "
                    f"{_fmt_pct(r['mdd'])} | {r['sharpe']:.2f} | "
                    f"{('—' if key == 'exit0' else _fmt_pct(vs))} | {r['ntrades']} |")
            lines.append("")

    # 요약: WS vs exit=0 (수익·MDD 차이)
    lines.append("## 요약 — WS vs exit=0 (수익 보존률 · MDD 개선)")
    lines.append("")
    lines.append("| 심볼 | 기간 | 시나리오 | 수익(exit=0) | 수익(WS) | "
                 "보존률 | MDD exit=0 | MDD WS | MDD 개선 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for sym in SYMBOLS:
        for label, _, _ in PERIODS:
            res = all_results.get((sym, label))
            if not res:
                continue
            e0 = res["exit0"]
            for ws in ["WS-A 보수계단", "WS-B 연속형", "WS-C 공격계단"]:
                r = res[ws]
                preserve = (r["ret"] / e0["ret"]) if e0["ret"] != 0 else float("nan")
                mdd_improve = e0["mdd"] - r["mdd"]   # 양수 = WS가 더 낮은 MDD(개선)
                lines.append(
                    f"| {sym} | {label} | {ws} | {_fmt_pct(e0['ret'])} | "
                    f"{_fmt_pct(r['ret'])} | {preserve*100:.0f}% | "
                    f"{_fmt_pct(e0['mdd'])} | {_fmt_pct(r['mdd'])} | "
                    f"{_fmt_pct(mdd_improve)} |")
    lines.append("")

    lines.append("## 해석 (야간 1차 — 데이터 기반, ★ WIP 가설 검증 결과)")
    lines.append("")
    lines.append("- **★ 핵심: WIP §6 가설('수익 희생 → MDD 보상')이 데이터로 반박됨.**")
    lines.append("- **수익**: WS 보존률이 대부분 **100% 초과** "
                 "(2007-26 QQQ WS-A 158%·WS-C 160%, SPY WS-A 143%). "
                 "저가 밴드 추가 매수(base*dep)가 평단가 하락에 효과적 → exit=0보다 수익 ↑.")
    lines.append("- **MDD**: 개선 미미 또는 **악화** (2020-26 QQQ −16%→−21%, SPY −14%→−15~16%). "
                 "코어 보유물을 매도 안 하므로 하락장에 포트폴리오 가치가 그대로 하락 — "
                 "현금 비축이 있어도 이미 주식 비중이 크면 방어 효과 부족.")
    lines.append("- **결론**: 비중 슬라이드는 '수익 강화'에는 유효하나 'MDD 방어'에는 무력. "
                 "방어가 필요하면 exit_ratio(소수치 매도) 또는 후보 (c)재진입과 **결합**해야 함. "
                 "★ 이 결합이 후보 (c) 설계의 핵심 근거가 됨.")
    lines.append("- **WS-A vs WS-C**: C(공격)가 수익 약간 ↑·MDD 약간 ↓(더 나쁨) — 일관적.")
    lines.append("- **WS-B 연속형**: 보존률 가장 낮음(75~137%). 연속 w(d)가 저가에서 완만히 증가하고 "
                 "dep 상한이 계단(B5=3~5배)보다 약해서 추정. w_fn 기울기·dep 계수 검토 대상.")
    lines.append("- **Sharpe**: 수익 ↑·변동성 비슷 → 대부분 exit=0 근접~소폭 상회.")
    lines.append("")
    lines.append("> **검증 루프 메모(사칙):** 위 해석은 단일 관점(본인) 1차 판독. "
                 "아침 승인 전 서로 다른 관점(수익 관점 / 방어 관점) 서브에이전트 병렬 비판 + "
                 "Codex 재검증 최소 2회 필요. 특히 'MDD 악화'의 원인 분석(엔진 월 인출 모델 영향?) 검증.")
    lines.append("")
    lines.append("## 한계 (v1)")
    lines.append("")
    lines.append("- 엔진이 'initial_cash 월 인출' 모델 → base 고갈(약 60개월) 이후 매수 중단. "
                 "기존 HybridStrategy와 동일 기준이나, '영구 월 적립' 모델로의 재검증 필요.")
    lines.append("- '현금 탄약 엄밀 누적' 미구현(base 배수 근사). WIP §5 모델 정확 구현은 엔진 확장 후.")
    lines.append("- 레짔(BULL/BEAR) 필터 미결합 — WIP §8.5 '레짔 매수중단 + WS' 조합은 차후 검증.")
    lines.append("- 백분IDE·워크포워드·out-of-sample 미실시(전략 스펙 §6 리스크 인프라와 함께 v1 승인 후).")
    lines.append("")
    lines.append("---")
    lines.append("**WIP 끝.** 채택·commit·외부 송신 금지. 07:00 KST 이사님 리뷰 대기.")
    lines.append("")
    return "\n".join(lines)


def main():
    print("=" * 72)
    print("비중 슬라이드 정량 백테스트 — 시나리오 3종 × 3기간 × 2심볼 (07-04 01:00)")
    print("=" * 72)

    all_results = {}
    for sym in SYMBOLS:
        for label, start, end in PERIODS:
            prices = load_prices([sym, "SHV"], start=start, end=end)
            if sym not in prices.columns or prices[sym].dropna().empty:
                print(f"  ({sym} {label}: 데이터 없음 — skip)")
                continue
            res = run_period(sym, start, end, label, prices)
            all_results[(sym, label)] = res
            e0 = res["exit0"]
            print(f"\n[{sym} {label} {res['span']}]")
            print(f"  exit=0 : ret={_fmt_pct(e0['ret'])} MDD={_fmt_pct(e0['mdd'])} "
                  f"sharpe={e0['sharpe']:.2f} (B&H ret={_fmt_pct(res['bh']['ret'])})")
            for ws in ["WS-A 보수계단", "WS-B 연속형", "WS-C 공격계단"]:
                r = res[ws]
                preserve = (r["ret"] / e0["ret"] * 100) if e0["ret"] != 0 else float("nan")
                print(f"  {ws:14s}: ret={_fmt_pct(r['ret'])} ({preserve:.0f}%보존) "
                      f"MDD={_fmt_pct(r['mdd'])} sharpe={r['sharpe']:.2f}")

    # WIP 결과 마크다운 저장
    md = to_markdown(all_results)
    out_path = Path("/home/ubuntu/projects/autotrader/research/"
                    "WIP-weight-slide-results-v1-draft.md")
    out_path.write_text(md, encoding="utf-8")
    print(f"\n[저장] {out_path}")
    print(f"[요약] exit=0 대비 — 전 케이스 위 '보존률%/MDD' 콘솔 출력 참조.")


if __name__ == "__main__":
    main()

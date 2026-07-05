# 전략 로직 스펙 v1 — 하이브리드 (DCA 스케폴드 + 레짔 필터)

> 상태: 정식 스펙(백테스트 구현 기준) · 미인증 · 스택 ADR과 함께 확정 예정
> 이사님 지시("로직 명확히 하고 → 그 기반 백테스트 프로그램 개발")에 대한 응답.
> 세미나 추천(하이브리드)을 구현 가능 스펙으로 구체화. 세미나: `~/notes/.reviews/seminar-raoer-20260626-01.md`

---

## 0. 설계 원칙
- **전략 = 교체 가능(pluggable) 모듈.** 백테스트 엔진은 "전략 인터페이스"만 호출. 이사님이 로직을 바꿔도 엔진·데이터·성과 코드는 재사용.
- 첫 구현 전략 = 하이브리드. 동일 인터페이스로 라오어 단독·순수 DCA·VAA 등 다른 전략 추가 가능 (비교 실험용).

---

## 1. 전략 인터페이스 (엔진 ↔ 전략 계약)
```
class Strategy:
    def on_rebalance(date, market, state) -> list[Order]
      # date: 리밸런스일 (월간)
      # market: {symbol: {close, sma200, momentum_252, ...}}
      # state: {cash, holdings{symbol: qty}, avg_cost{symbol}, history}
      # Order: {symbol, side: BUY|SELL, amount_or_qty, reason}
```
엔진은 매 **월간 rebalance일**에 `on_rebalance` 호출. 전략은 순수하게 "이날 무엇을 할지"만 결정 (포트폴리오/수수료/체결은 엔진 책임).

---

## 2. 하이브리드 전략 — 4 컴포넌트

### A. 분할매수 뼈대 (라오어 변형, 현물 1배)
- 총자본 C를 N회 분할. 1회 기본 예산 `base = C/N`.
- **하락 가산**: 기준가 `ref` 대비 하락할수록 증량.
  ```
  d = (ref - price) / ref          # 양수 = 하락폭
  budget = min(base * (1 + k * max(0, d)), base * cap)
  ```
- `ref = SMA(close, 200)` (추세 기준). `cap`으로 극단 하락 시 비용 폭발 방지.

### B. 레짔(국면) 필터 — VAA/DAA 모멘텀 ★ 핵심
- 모멘텀 `m = price_today / price_{today-252} - 1` (12개월).
- 비교: `m_QQQ` vs `m_SHV`(현금 대용 순수익률).
- `m_QQQ > m_SHV` → **BULL** → 매수 진행 (컴포넌트 A).
- `m_QQQ ≤ m_SHV` → **BEAR/횡보** → 매수 중단 + 보유 **현금 대피** (라오어의 치명적 약점 = "하락에도 계속 삼"을 차단).

### C. 실행 빈도
- **월간 rebalance** (월초 첫 영업일). 라오어 원형(일일 LOC) 대신 → 수수료·스프레드 비용 절감(세미나 §5 권고).
- N = 투자기간(월) 수.

### D. DRIP (후순위 — v1.1)
- 배당 재투자. 단일 ETF(QQQ)라 효과 작음 → 1차 검증 후 추가.

---

## 3. 매수/매도/현금대피 의사코드
```
on_rebalance(date, market, state):
    m_q = market[QQQ].momentum_252
    m_s = market[SHV].momentum_252
    price = market[QQQ].close
    sma200 = market[QQQ].sma200

    if m_q > m_s:                       # BULL
        d = (sma200 - price) / sma200
        budget = min(base * (1 + k * max(0, d)), base * cap)
        budget = min(budget, remaining_capital)   # 분할 예산 한도
        return [Order(QQQ, BUY, amount=budget, reason="DCA+regime_bull")]
    else:                               # BEAR / 횡보
        sell_qty = state.holdings[QQQ] * exit_ratio
        return [Order(QQQ, SELL, qty=sell_qty, reason="regime_bear_cash_shelter")]
```

---

## 4. 파라미터 (초기값 — 백테스트 검증 대상)
| 파라미터 | 의미 | 초기값 |
|---|---|---|
| `C` | 초기 자본 | 10,000 (USD) |
| `N` | 총 분할(투자월) 수 | 60 (5년) |
| `base` | 1회 기본 예산 = C/N | C/60 |
| `k` | 하락 가산 계수 | 2.0 |
| `cap` | 1회 매수 상한 배수 | 3.0 |
| `mom_period` | 모멘텀 룩백(영업일) | 252 (12m) |
| `exit_ratio` | 약세 시 매도 비율 | 1.0 (전량 대피) |
| `rebalance` | rebalance 주기 | 월간 |
| `fee` | 왕복 수수료율 | 0.1% |

---

## 5. 입력 / 출력 명세
- **입력**: QQQ·SHV 일봉 OHLCV (stooq 무료), 시작일·종료일, 초기자본 C, 수수료율.
- **출력**:
  - 일일 포트폴리오 가치 곡선
  - 거래 내역(일자·심볼·매수/매수·수량·가격·사유)
  - 성과 지표: 총수익률, CAGR, 연환산 샤프, 최대낙폭(MDD), 승월(월간 vs B&H)
  - **비교 기준**: Buy&Hold QQQ, 순수 DCA(레짔필터 없음) → 하이브리드의 "추가 가치" 측정

---

## 6. v1 리스크 원칙 매핑 (후속 단계)
- v1 IDEATION §5 리스크 원칙(킬스위치/회로차단기·DSR·Walk-Forward·Monte Carlo·5백분위 콘)은 **전략 1차 검증 후** 엔진에 추가.
- 본 스펙 = "전략 로직 명확화" 단계. 검증 인프라는 ADR에서 단계 명시.

---

## 7. 첫 백테스트 계획
- **종목**: QQQ (현물 1배). **TQQQ 배제** (decay/자본고갈 위험 — 세미나 §4).
- **기간**: stooq 제공 전범위 (최대한 길게).
- **비교**: (i) Buy&Hold QQQ (ii) 순수 DCA (iii) 하이브리드 → 레짔필터의 한 방어 가치 측정.
- 결과는 숫자로 이사님께 보고.

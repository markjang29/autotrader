"""autotrader 백테스트 패키지.

- data:       가격 데이터 로더(yfinance + CSV 캐시)
- engine:     백테스트 엔진(월간 rebalance, 포트폴리오, 성과 지표)
- strategies: 전략 모듈(pluggable) — 하이브리드 / 순수 DCA / Buy&Hold
"""

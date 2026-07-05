"""autotrader 백데이터 시뮬레이터 REST API — FastAPI (포트 8001).

엔드포인트:
    GET  /strategies           — 전략 목록
    POST /backtest             — 단일 실행 또는 exit_ratio 자동비교 모드

기존 backtest/{data,engine,strategies} 3-레이어 재사용.
"""

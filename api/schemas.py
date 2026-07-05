"""요청/응답 스키마 (pydantic)."""
from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    strategy: Literal["hybrid", "dca", "buyhold"] = "hybrid"
    initial_cash: float = Field(10_000, description="초기 자본(USD)")
    splits: int = Field(60, description="분할 수(기본 5년)")
    base: Optional[float] = Field(None, description="1회 기본 예산(미지정 시 initial_cash/splits)")
    k: float = 2.0              # 하락 가산 계수
    cap: float = 3.0            # 1회 매수 상한 배수
    exit_ratio: float = 1.0     # 약세 시 매도 비율(1.0=전량)
    symbols: list[str] = Field(default_factory=lambda: ["QQQ"])
    benchmark: str = "SHV"      # 하이브리드 레짔 벤치마크
    start: date = date(2010, 1, 1)
    end: date = date(2026, 6, 26)
    compare_exit_ratios: Optional[list[float]] = None   # 자동비교 모드


class MetricsOut(BaseModel):
    final: float
    total_return: float
    cagr: float
    sharpe: float
    mdd: float


class EquityPoint(BaseModel):
    date: str
    value: float


class TradeOut(BaseModel):
    date: str
    symbol: str
    side: str
    qty: float
    price: float
    reason: str


class BacktestResult(BaseModel):
    strategy: str
    exit_ratio: float
    params: dict
    metrics: MetricsOut
    n_buys: int
    n_sells: int
    equity_curve: list[EquityPoint]
    trades: list[TradeOut]


class CompareResult(BaseModel):
    strategy: str
    target: str
    benchmark: str
    results: list[BacktestResult]

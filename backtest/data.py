"""가격 데이터 로더 — yfinance + CSV 캐시.

데이터 소스: yfinance(Yahoo). rate limit 대비 로컬 CSV 캐시.
전략 스펙: ~/projects/autotrader/strategy-spec-v1.md §5
"""
from pathlib import Path
import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).resolve().parent.parent / "data_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_prices(symbols, start="2010-01-01", end="2026-06-26"):
    """심볼 리스트의 일별 종가 DataFrame을 반환(컬럼 = 심볼). 캐시 우선."""
    sym_key = "_".join(symbols)
    cache_file = CACHE_DIR / f"{sym_key}_{start}_{end}.csv"

    if cache_file.exists():
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
    else:
        raw = yf.download(symbols, start=start, end=end, progress=False, auto_adjust=True)
        close = raw["Close"]
        if isinstance(close, pd.Series):
            close = close.to_frame(name=symbols[0])
        close = close.dropna()
        close.to_csv(cache_file)
        df = close

    # 요청 심볼만 보장
    return df[[s for s in symbols if s in df.columns]]


if __name__ == "__main__":
    p = load_prices(["QQQ", "SHV"])
    print(p.shape, p.index.min().date(), "->", p.index.max().date())
    print(p.tail(3))

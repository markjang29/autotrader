"""FastAPI 앱 — 백데이터 시뮬레이터 REST API (포트 8001).

실행:
    /home/ubuntu/.venvs/autotrader/bin/uvicorn --app-dir /home/ubuntu/projects/autotrader api.main:app --port 8001
"""
from fastapi import FastAPI, HTTPException

from backtest.data import load_prices
from backtest.engine import run_backtest, metrics
from backtest.strategies import HybridStrategy, DCAStrategy, BuyHoldStrategy
from api.schemas import BacktestRequest, MetricsOut
from api.repository import get_repo

app = FastAPI(title="autotrader 백테스트 시뮬레이터", version="0.1.0")
_repo = get_repo()

STRATEGY_MAP = {
    "hybrid": ("하이브리드(라오어 분할매수 + 레짔 필터)", HybridStrategy),
    "dca": ("순수 DCA(레짔필터 없음)", DCAStrategy),
    "buyhold": ("Buy & Hold(벤치마크)", BuyHoldStrategy),
}


@app.get("/strategies")
def list_strategies():
    return [{"name": k, "description": v[0]} for k, v in STRATEGY_MAP.items()]


@app.post("/backtest")
def run_bt(req: BacktestRequest):
    target = (req.symbols or ["QQQ"])[0]
    bench = req.benchmark

    # 하이브리드는 레짔 벤치마크 필요 → 자동 추가
    syms = [target] + ([bench] if (req.strategy == "hybrid" and bench != target) else [])
    syms = list(dict.fromkeys(syms))

    try:
        prices = load_prices(syms, start=str(req.start), end=str(req.end))
    except Exception as e:
        raise HTTPException(400, f"데이터 로드 실패: {e}")
    if target not in prices.columns:
        raise HTTPException(400, f"{target} 가격 데이터 없음")

    base = req.base if req.base else req.initial_cash / req.splits
    params = {"base": base, "k": req.k, "cap": req.cap}
    ratios = req.compare_exit_ratios if req.compare_exit_ratios else [req.exit_ratio]
    cls = STRATEGY_MAP[req.strategy][1]

    out = []
    for er in ratios:
        p = dict(params)
        p["exit_ratio"] = er
        strat = cls(p, target=target, benchmark=bench)
        pv, trades = run_backtest(strat, prices, req.initial_cash, fee=0.001)
        m = metrics(pv, req.initial_cash)
        eq = [{"date": d.strftime("%Y-%m-%d"), "value": float(v)}
              for d, v in pv.resample("ME").last().dropna().items()]
        tr_out = [{"date": t[0].strftime("%Y-%m-%d"), "symbol": t[1], "side": t[2],
                   "qty": float(t[3]), "price": float(t[4]), "reason": t[5]} for t in trades]
        out.append({
            "strategy": req.strategy,
            "exit_ratio": er,
            "params": {**p, "initial_cash": req.initial_cash, "splits": req.splits},
            "metrics": m,
            "n_buys": sum(1 for t in trades if t[2] == "BUY"),
            "n_sells": sum(1 for t in trades if t[2] == "SELL"),
            "equity_curve": eq,
            "trades": tr_out,
        })
        _repo.save_run(
            {"strategy": req.strategy, "symbols": req.symbols, "target": target,
             "base": base, "k": req.k, "cap": req.cap, "exit_ratio": er,
             "start": str(req.start), "end": str(req.end)},
            {"metrics": m},
        )

    if req.compare_exit_ratios:
        return {"strategy": req.strategy, "target": target, "benchmark": bench, "results": out}
    return out[0]


@app.get("/health")
def health():
    return {"status": "ok", "repo": type(_repo).__name__}

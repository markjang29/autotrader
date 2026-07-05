"""이사님용 백테스트 대시보드 — 비금융 전문가 친화적. Streamlit (포트 8002).

backtest 엔진 재사용. 금융 용어는 모두 풀어씀.
실행: /home/ubuntu/.venvs/autotrader/bin/streamlit run dashboard.py --server.port 8002 --server.address 0.0.0.0
"""
import sys
sys.path.insert(0, "/home/ubuntu/projects/autotrader")
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from backtest.data import load_prices
from backtest.engine import run_backtest, metrics
from backtest.strategies import HybridStrategy, DCAStrategy, BuyHoldStrategy

st.set_page_config(page_title="자동매매 전략 실험실", page_icon="📊", layout="wide")

STRAT = {
    "하이브리드 (추천)": ("hybrid", "시장이 좋을 땐 적립식 매수, 나쁠 땐 일부를 현금화해 방어. (라오어식 + 안전장치)"),
    "순수 적립식 (DCA)": ("dca", "시장 상황 상관없이 매달 같은 금액 매수. 가장 단순."),
    "사고보유 (Buy & Hold)": ("buyhold", "처음에 전액 매수 후 끝까지 보유. 비교 기준."),
}
PERIODS = {
    "최근 5년 (2021~)": ("2021-01-01", "2026-06-26"),
    "최근 10년 (2016~)": ("2016-01-01", "2026-06-26"),
    "최근 15년 (2011~)": ("2011-01-01", "2026-06-26"),
    "전체 (2007~)": ("2007-01-01", "2026-06-26"),
}
SYMS = {"QQQ — 나스닥100 (기술주 중심)": "QQQ", "SPY — S&P500 (미국 대형주)": "SPY"}
INITIAL = 10_000

st.title("📊 자동매매 전략 실험실")
st.markdown("전략과 조건을 바꿔가며 **과거 데이터에서 '돈을 얼마나 벌었을까'**를 직접 실험하세요. 금융 용어는 모두 풀어 썼습니다.")

with st.sidebar:
    st.header("⚙️ 실험 설정")
    sname = st.radio("전략 선택", list(STRAT.keys()))
    st.caption(STRAT[sname][1])
    strategy = STRAT[sname][0]
    sym_label = st.selectbox("투자 종목", list(SYMS.keys()))
    sym = SYMS[sym_label]
    plabel = st.selectbox("투자 기간", list(PERIODS.keys()))
    start, end = PERIODS[plabel]
    auto = st.checkbox("여러 강도로 한번에 비교 (추천)", value=True,
                       help="하락장 대응 강도 5단계(0%~100%)를 한번에 돌려 비교합니다.")
    if auto:
        ratios = [0.0, 0.3, 0.5, 0.7, 1.0]
    else:
        er = st.slider("🛡️ 하락장 대응 강도", 0.0, 1.0, 0.5, 0.1,
                       help="시장이 하락할 때 얼마나 팔지. **0% = 끝까지 버티고 계속 삼**, **100% = 위험 오면 전액 현금화**.")
        ratios = [er]
    run_btn = st.button("🚀 백테스트 실행", type="primary", use_container_width=True)

with st.expander("📖 결과 지표 읽는 법 (금융 용어 풀이)"):
    st.markdown("""
- **최종 자산**: 처음 $10,000가 결과적으로 얼마가 됐나.
- **수익률**: 번 돈의 비율. +100% = 2배.
- **최대낙폭(MDD)**: 투자 중 **가장 크게 빠졌던 구간**. -35%면 자산이 35% 깎였다가 회복한 것. **작을수록 안전**.
- **위험대비수익(Sharpe)**: 위험을 감당한 만큼 얼마를 벌었나. **1 이상=양호, 2 이상=매우 좋음**.
- **하락장 대응 강도**: 시장 하락 시 팔 비율. 0%=버티고 계속 삼, 100%=전액 현금화.
""")

if run_btn:
    with st.spinner("과거 데이터를 불러와 시뮬레이션 중..."):
        prices = load_prices([sym, "SHV"], start=start, end=end)
        if sym not in prices.columns:
            st.error(f"{sym} 데이터를 불러오지 못했습니다.")
            st.stop()
        base = INITIAL / 60
        bh = BuyHoldStrategy({"base": base}, target=sym, benchmark="SHV")
        pv_bh, _ = run_backtest(bh, prices, INITIAL, 0.001)
        mbh = metrics(pv_bh, INITIAL)
        cls_map = {"hybrid": HybridStrategy, "dca": DCAStrategy, "buyhold": BuyHoldStrategy}
        StratCls = cls_map[strategy]
        rows, fig = [], go.Figure()
        fig.add_trace(go.Scatter(x=pv_bh.index, y=pv_bh.values, name="사고보유(B&H)",
                                 line=dict(width=2, color="gray", dash="dot")))
        for er in ratios:
            p = {"base": base, "k": 2.0, "cap": 3.0, "exit_ratio": er}
            strat = StratCls(p, target=sym, benchmark="SHV")
            pv, trades = run_backtest(strat, prices, INITIAL, 0.001)
            m = metrics(pv, INITIAL)
            rows.append({
                "하락장대응강도": f"{int(er*100)}%",
                "최종자산($)": round(m["final"]),
                "수익률": m["total_return"],
                "최대낙폭(MDD)": m["mdd"],
                "위험대비수익(Sharpe)": round(m["sharpe"], 2),
                "매수": sum(1 for t in trades if t[2] == "BUY"),
                "매도": sum(1 for t in trades if t[2] == "SELL"),
            })
            fig.add_trace(go.Scatter(x=pv.index, y=pv.values, name=f"강도 {int(er*100)}%"))
        fig.update_layout(title="💰 자산 변화 (시간이 지남에 따라)",
                          xaxis_title="날짜", yaxis_title="자산($)",
                          height=460, hovermode="x unified", legend_title="범례")

    df = pd.DataFrame(rows)
    best = df.loc[df["수익률"].idxmax()]            # 수익 최고
    safest = df.loc[df["최대낙폭(MDD)"].idxmax()]   # MDD 음수 → max = 가장 작은 낙폭 = 가장 안전
    best_sharpe_row = df.loc[df["위험대비수익(Sharpe)"].idxmax()]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📊 사고보유(B&H) 수익률", f"{mbh['total_return']*100:.1f}%", f"MDD {mbh['mdd']*100:.1f}%")
    c2.metric("🏆 최고 수익률", f"{best['수익률']*100:.1f}%", f"강도 {best['하락장대응강도']}")
    c3.metric("🛡️ 가장 안전(낙폭 最小)", f"{safest['수익률']*100:.1f}%", f"MDD {safest['최대낙폭(MDD)']*100:.1f}%")
    c4.metric("⚖️ 위험대비수익 최고", f"{best_sharpe_row['위험대비수익(Sharpe)']}", f"강도 {best_sharpe_row['하락장대응강도']}")

    st.subheader("결과 비교표")
    disp = df.copy()
    disp["수익률"] = (disp["수익률"] * 100).round(1).astype(str) + "%"
    disp["최대낙폭(MDD)"] = (disp["최대낙폭(MDD)"] * 100).round(1).astype(str) + "%"
    st.dataframe(disp, use_container_width=True, hide_index=True)

    st.plotly_chart(fig, use_container_width=True)
    st.info(f"💡 이 조건({sname.split()[0]} · {sym} · {plabel})에서는 **하락장 대응 강도 {best['하락장대응강도']}**일 때 "
            f"수익률이 가장 높았습니다({best['수익률']*100:.1f}%). 단, 강도가 낮을수록(버틸수록) 수익은 크지만 "
            f"**최대낙폭도 커집니다** — 위험을 더 안는 대가입니다.")
else:
    st.info("👈 왼쪽 설정에서 전략·종목·기간을 고르고 **🚀 백테스트 실행**을 누르세요.")

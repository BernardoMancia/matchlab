import os
import json
import pandas as pd
import streamlit as st
from datetime import date, timedelta

from app.config import DB_PATH
from app.db import conn, init_db

st.set_page_config(page_title="MatchLab Dashboard", layout="wide")
init_db()

st.title("MatchLab — Predictions & Backtest")

st.sidebar.header("Filtros")
limit = st.sidebar.slider("Últimas previsões", 10, 200, 50)

c = conn()
preds = pd.read_sql_query("""
  SELECT p.id, p.fixture_id, p.created_at_iso, p.scoreline, p.confidence,
         m.kickoff_iso, m.home_name, m.away_name, m.home_goals, m.away_goals
  FROM predictions p
  LEFT JOIN matches m ON m.fixture_id = p.fixture_id
  ORDER BY p.id DESC
  LIMIT ?
""", c, params=(limit,))
bt = pd.read_sql_query("SELECT * FROM backtest_runs ORDER BY id DESC LIMIT 20", c)
c.close()

col1, col2 = st.columns(2)
with col1:
    st.subheader("Últimas previsões")
    st.dataframe(preds, use_container_width=True)

with col2:
    st.subheader("Backtests recentes")
    if not bt.empty:
        bt2 = bt.copy()
        bt2["metrics_json"] = bt2["metrics_json"].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
        st.dataframe(bt2[["created_at_iso","league_id","season","from_date","to_date","metrics_json"]], use_container_width=True)
    else:
        st.info("Nenhum backtest rodado ainda.")

st.divider()
st.subheader("Métricas rápidas (em cima das previsões carregadas)")

def parse_score(s):
    import re
    m = re.search(r"(\d+)\s*[–-]\s*(\d+)", str(s))
    if not m: return None
    return int(m.group(1)), int(m.group(2))

finished = preds.dropna(subset=["home_goals","away_goals"])
finished = finished[finished["home_goals"].apply(lambda x: isinstance(x, (int, float)))]

if finished.empty:
    st.warning("Sem resultados finais gravados no DB. (Você ainda não está atualizando placar final no matches.)")
else:

    ok = 0
    exact = 0
    total = 0
    for _, r in finished.iterrows():
        ps = parse_score(r["scoreline"])
        if not ps: 
            continue
        ph, pa = ps
        hg, ag = int(r["home_goals"]), int(r["away_goals"])
        total += 1
        if ph == hg and pa == ag: exact += 1
        real = 0 if hg==ag else (1 if hg>ag else -1)
        pred = 0 if ph==pa else (1 if ph>pa else -1)
        if real == pred: ok += 1

    c1, c2, c3 = st.columns(3)
    c1.metric("Jogos finalizados analisáveis", total)
    c2.metric("Acerto resultado (W/D/L)", f"{(ok/total)*100:.1f}%")
    c3.metric("Acerto placar exato", f"{(exact/total)*100:.1f}%")

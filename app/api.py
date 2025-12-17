from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

from .db import init_db, conn
from .dossier import build_dossier
from .predictors import predict_and_store
from .backtest import run_backtest
from .web import router as web_router

app = FastAPI(title="MatchLab", version="1.1.0")

@app.on_event("startup")
def _startup():
    init_db()

app.include_router(web_router)

class PredictReq(BaseModel):
    home: str
    away: str
    kickoff: str
    tz: Optional[str] = "America/Sao_Paulo"
    season: int
    league_id: Optional[int] = None
    recent_n: int = 5
    h2h_n: int = 10
    mode: str = "full"

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/predict")
def predict(req: PredictReq):
    dossier = build_dossier(
        home=req.home,
        away=req.away,
        kickoff=req.kickoff,
        tz=req.tz,
        season=req.season,
        league_id=req.league_id,
        recent_n=req.recent_n,
        h2h_n=req.h2h_n,
    )
    result = predict_and_store(dossier, mode=req.mode)
    return result

@app.get("/predictions/latest")
def latest(limit: int = 20):
    c = conn()
    rows = c.execute("""
      SELECT id, fixture_id, created_at_iso, scoreline, confidence
      FROM predictions ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    c.close()
    return {"items": [dict(r) for r in rows]}

class BacktestReq(BaseModel):
    league_id: int
    season: int
    from_date: str
    to_date: str

@app.post("/backtest/run")
def backtest(req: BacktestReq):
    metrics = run_backtest(req.league_id, req.season, req.from_date, req.to_date)
    return {"metrics": metrics}

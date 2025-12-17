import json
import re
from datetime import datetime
from .providers.openai_client import analyze_with_openai
from .db import conn

PLACAR_RE = re.compile(r"PLACAR_MAIS_PROVAVEL:\s*(.+)", re.IGNORECASE)

def save_match_if_needed(dossier: dict):
    m = dossier["match"]
    c = conn()
    c.execute("""
    INSERT OR REPLACE INTO matches(fixture_id, league_id, season, kickoff_iso, home_name, away_name, home_id, away_id, status, raw_json)
    VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (
        m["fixture_id"],
        m["league"].get("id"),
        m["season"],
        m["kickoff_local"],
        m["home"]["name"],
        m["away"]["name"],
        m["home"]["id"],
        m["away"]["id"],
        None,
        json.dumps(dossier, ensure_ascii=False),
    ))
    c.commit()
    c.close()

def extract_scoreline(report: str) -> str:
    m = PLACAR_RE.search(report)
    return m.group(1).strip() if m else "DADO AUSENTE"

def extract_confidence(report: str) -> int:
    m = re.findall(r"Confian[çc]a\s*[:\-]\s*(\d+)", report, flags=re.IGNORECASE)
    if not m: return 0
    v = int(m[-1])
    return max(0, min(100, v))

def predict_and_store(dossier: dict, mode: str = "full") -> dict:
    save_match_if_needed(dossier)

    report = analyze_with_openai(json.dumps(dossier, ensure_ascii=False), mode=mode)
    scoreline = extract_scoreline(report)
    confidence = extract_confidence(report)

    c = conn()
    c.execute("""
    INSERT INTO predictions(fixture_id, created_at_iso, model, dossier_json, report_text, scoreline, confidence, risk_json)
    VALUES(?,?,?,?,?,?,?,?)
    """, (
        dossier["match"]["fixture_id"],
        datetime.utcnow().isoformat(),
        "openai",
        json.dumps(dossier, ensure_ascii=False),
        report,
        scoreline,
        confidence,
        "[]",
    ))
    c.commit()
    c.close()

    return {
        "fixture_id": dossier["match"]["fixture_id"],
        "home": dossier["match"]["home"]["name"],
        "away": dossier["match"]["away"]["name"],
        "kickoff_local": dossier["match"]["kickoff_local"],
        "report": report,
        "scoreline": scoreline,
        "confidence": confidence,
    }

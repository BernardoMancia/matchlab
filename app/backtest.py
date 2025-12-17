import json
from datetime import datetime
from typing import Dict, Any, List, Tuple
from .db import conn
from .providers.apifootball import APIFootball

def _parse_scoreline(scoreline: str) -> Tuple[int, int]:
    import re
    m = re.search(r"(\d+)\s*[–-]\s*(\d+)", scoreline)
    if not m:
        return (-1, -1)
    return (int(m.group(1)), int(m.group(2)))

def run_backtest(league_id: int, season: int, from_date: str, to_date: str) -> Dict[str, Any]:
    api = APIFootball()
    try:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d").date()
        to_dt = datetime.strptime(to_date, "%Y-%m-%d").date()
        days = []
        d = from_dt
        while d <= to_dt:
            days.append(d.isoformat())
            d = d.fromordinal(d.toordinal() + 1)

        fixtures: List[dict] = []
        for day in days:
            fixtures.extend(api.fixtures_by_date_league(day, league_id, season, timezone=None))

        c = conn()
        preds = c.execute("""
          SELECT fixture_id, scoreline
          FROM predictions
          WHERE fixture_id IN (%s)
        """ % ",".join(["?"] * len({fx["fixture"]["id"] for fx in fixtures})),
        [fx["fixture"]["id"] for fx in fixtures]).fetchall() if fixtures else []
        c.close()

        pred_map = {row["fixture_id"]: row["scoreline"] for row in preds}

        total = 0
        exact = 0
        outcome = 0
        missing = 0

        for fx in fixtures:
            fid = fx["fixture"]["id"]
            status = fx["fixture"]["status"]["short"]
            goals = fx.get("goals", {})
            hg, ag = goals.get("home"), goals.get("away")
            if status not in ("FT", "AET", "PEN"):  # finalizados
                continue
            if hg is None or ag is None:
                continue

            total += 1
            if fid not in pred_map:
                missing += 1
                continue

            ph, pa = _parse_scoreline(pred_map[fid])
            if ph < 0:
                continue

            if ph == hg and pa == ag:
                exact += 1

            real = 0 if hg == ag else (1 if hg > ag else -1)
            pred = 0 if ph == pa else (1 if ph > pa else -1)
            if real == pred:
                outcome += 1

        metrics = {
            "total_finished": total,
            "predictions_found": total - missing,
            "exact_score_accuracy": (exact / (total - missing)) if (total - missing) > 0 else 0.0,
            "outcome_accuracy": (outcome / (total - missing)) if (total - missing) > 0 else 0.0,
        }

        c = conn()
        c.execute("""
          INSERT INTO backtest_runs(created_at_iso, league_id, season, from_date, to_date, metrics_json)
          VALUES(?,?,?,?,?,?)
        """, (
            datetime.utcnow().isoformat(),
            league_id, season, from_date, to_date,
            json.dumps(metrics, ensure_ascii=False),
        ))
        c.commit()
        c.close()

        return metrics

    finally:
        api.close()

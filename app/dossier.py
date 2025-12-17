from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional

from .cache import cache_get, cache_set
from .providers.apifootball import APIFootball
from .providers.xg_stub import XGStub
from .config import APP_TZ

def _key(*parts) -> str:
    return " | ".join(map(str, parts))

def find_fixture(api: APIFootball, home_id: int, away_id: int, kickoff_local: datetime, season: int, tz: str):
    days = [
        kickoff_local.date() - timedelta(days=1),
        kickoff_local.date(),
        kickoff_local.date() + timedelta(days=1),
    ]
    for d in days:
        fixtures = api.fixtures_by_team_date(home_id, d.isoformat(), season, tz)
        for fx in fixtures:
            th = fx.get("teams", {}).get("home", {}).get("id")
            ta = fx.get("teams", {}).get("away", {}).get("id")
            if th == home_id and ta == away_id:
                return fx
    raise RuntimeError("Fixture não encontrado. Ajuste timezone/season/nomes dos times.")

def summarize_recent(fixtures, team_id: int):
    out = []
    W = D = L = GF = GA = 0

    for fx in fixtures:
        teams = fx.get("teams", {})
        goals = fx.get("goals", {})
        hg, ag = goals.get("home"), goals.get("away")
        if hg is None or ag is None:
            continue

        home_id = teams.get("home", {}).get("id")
        is_home = (home_id == team_id)
        opp = teams.get("away") if is_home else teams.get("home")

        my_g = hg if is_home else ag
        op_g = ag if is_home else hg

        GF += my_g or 0
        GA += op_g or 0

        if my_g > op_g:
            W += 1
            r = "W"
        elif my_g < op_g:
            L += 1
            r = "L"
        else:
            D += 1
            r = "D"

        out.append({
            "date": fx.get("fixture", {}).get("date"),
            "vs": opp.get("name"),
            "H/A": "H" if is_home else "A",
            "score": f"{hg}-{ag}",
            "result": r
        })

    return {"W": W, "D": D, "L": L, "GF": GF, "GA": GA, "matches": out}

def extract_table_row(standings_payload, team_id: int):
    if not standings_payload:
        return None
    league = standings_payload[0].get("league", {})
    for group in league.get("standings", []):
        for row in group:
            if row.get("team", {}).get("id") == team_id:
                return row
    return None

def build_dossier(
    home: str,
    away: str,
    kickoff: str,
    tz: Optional[str],
    season: int,
    league_id: Optional[int],
    recent_n: int,
    h2h_n: int,
) -> Dict[str, Any]:

    tz = tz or APP_TZ
    kickoff_local = datetime.strptime(kickoff, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz))

    api = APIFootball()
    xg = XGStub()

    try:
        home_team = api.team_search(home)
        away_team = api.team_search(away)
        home_id, away_id = home_team["id"], away_team["id"]

        ck = _key("dossier", home_id, away_id, kickoff_local.isoformat(), season, league_id, recent_n, h2h_n)
        cached = cache_get(ck)
        if cached:
            return cached

        fixture = find_fixture(api, home_id, away_id, kickoff_local, season, tz)
        fixture_id = fixture.get("fixture", {}).get("id")

        league = fixture.get("league", {})
        resolved_league_id = league_id or league.get("id")

        lineups = api.lineups(fixture_id)
        injuries = api.injuries(fixture_id)
        stats = api.statistics(fixture_id)
        h2h = api.h2h(home_id, away_id, last=h2h_n)

        home_recent = api.last_fixtures(home_id, season=season, last=recent_n)
        away_recent = api.last_fixtures(away_id, season=season, last=recent_n)

        standings = api.standings(resolved_league_id, season=season) if resolved_league_id else []
        home_row = extract_table_row(standings, home_id)
        away_row = extract_table_row(standings, away_id)

        xg_ctx = xg.get_match_xg_context(
            home=home_team["name"],
            away=away_team["name"],
            kickoff_iso=fixture.get("fixture", {}).get("date"),
        )

        dossier = {
            "match": {
                "fixture_id": fixture_id,
                "kickoff_local": kickoff_local.isoformat(),
                "timezone": tz,
                "season": season,
                "league": league,
                "venue": fixture.get("fixture", {}).get("venue"),
                "home": {"id": home_id, "name": home_team["name"]},
                "away": {"id": away_id, "name": away_team["name"]},
            },
            "standings": {"home_row": home_row, "away_row": away_row},
            "recent_form": {
                "home": summarize_recent(home_recent, home_id),
                "away": summarize_recent(away_recent, away_id),
            },
            "head_to_head": {"last_n": h2h_n, "fixtures": h2h},
            "lineups": {"raw": lineups, "note": "Se vazio, lineup oficial ainda não saiu."},
            "injuries": injuries,
            "fixture_statistics": stats,
            "xg": xg_ctx,
        }

        cache_set(ck, dossier)
        return dossier

    finally:
        api.close()

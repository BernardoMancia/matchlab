import httpx
from typing import Any, Dict, List, Optional
from ..config import APIFOOTBALL_KEY, APIFOOTBALL_BASE_URL

class APIFootball:
    def __init__(self):
        if not APIFOOTBALL_KEY:
            raise RuntimeError("APIFOOTBALL_KEY não definido.")
        self.client = httpx.Client(
            base_url=APIFOOTBALL_BASE_URL,
            headers={"x-apisports-key": APIFOOTBALL_KEY, "Accept": "application/json"},
            timeout=25.0
        )

    def close(self):
        self.client.close()

    def _get(self, path: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        r = self.client.get(path, params=params)
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            raise RuntimeError(f"API-Football errors: {data['errors']}")
        return data.get("response", [])

    def team_search(self, name: str):
        res = self._get("/teams", {"search": name})
        if not res:
            raise RuntimeError(f"Time não encontrado: {name}")
        return res[0]["team"]

    def fixtures_by_date_league(self, day: str, league_id: int, season: int, timezone: Optional[str] = None):
        p = {"date": day, "league": league_id, "season": season}
        if timezone: p["timezone"] = timezone
        return self._get("/fixtures", p)

    def fixtures_by_team_date(self, team_id: int, day: str, season: int, timezone: Optional[str] = None):
        p = {"team": team_id, "date": day, "season": season}
        if timezone: p["timezone"] = timezone
        return self._get("/fixtures", p)

    def lineups(self, fixture_id: int):
        return self._get("/fixtures/lineups", {"fixture": fixture_id})

    def injuries(self, fixture_id: int):
        return self._get("/injuries", {"fixture": fixture_id})

    def statistics(self, fixture_id: int):
        return self._get("/fixtures/statistics", {"fixture": fixture_id})

    def h2h(self, home_id: int, away_id: int, last: int = 10):
        return self._get("/fixtures/headtohead", {"h2h": f"{home_id}-{away_id}", "last": last})

    def last_fixtures(self, team_id: int, season: int, last: int = 5):
        return self._get("/fixtures", {"team": team_id, "season": season, "last": last})

    def standings(self, league_id: int, season: int):
        return self._get("/standings", {"league": league_id, "season": season})

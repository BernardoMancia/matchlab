import os
import httpx


class APIFootball:
    def __init__(self):
        self.base_url = os.getenv("APIFOOTBALL_BASE_URL", "https://v3.football.api-sports.io")
        self.key = os.getenv("APIFOOTBALL_KEY")
        if not self.key:
            raise RuntimeError("APIFOOTBALL_KEY não definido no ambiente (.env).")

        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=30.0,
            headers={
                "x-apisports-key": self.key,
                "Accept": "application/json",
            },
        )

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass

    def _get(self, path: str, params: dict):
        r = self.client.get(path, params=params)
        r.raise_for_status()
        data = r.json()

        errors = data.get("errors") or {}
        if errors:
            # Detecta erro típico do plano Free: season fora do range
            if isinstance(errors, dict) and "plan" in errors:
                raise RuntimeError(f"APIFOOTBALL_PLAN_LIMIT: {errors.get('plan')}")
            raise RuntimeError(f"APIFOOTBALL_ERROR: {errors}")

        return data.get("response", [])

    # --------- Endpoints usados pelo projeto ---------

    def team_search(self, name: str) -> dict:
        resp = self._get("/teams", {"search": name})
        if not resp:
            raise RuntimeError(f"Time não encontrado na API-Football: {name}")
        # primeiro match
        return resp[0].get("team") or resp[0].get("teams") or resp[0]

    def fixtures_by_team_date(self, team_id: int, date_iso: str, season: int, tz: str):
        # date_iso: YYYY-MM-DD
        p = {"team": team_id, "date": date_iso, "season": season, "timezone": tz}
        return self._get("/fixtures", p)

    def last_fixtures(self, team_id: int, season: int, last: int = 5):
        p = {"team": team_id, "season": season, "last": last}
        return self._get("/fixtures", p)

    def h2h(self, home_id: int, away_id: int, last: int = 10):
        p = {"h2h": f"{home_id}-{away_id}", "last": last}
        return self._get("/fixtures/headtohead", p)

    def lineups(self, fixture_id: int):
        return self._get("/fixtures/lineups", {"fixture": fixture_id})

    def injuries(self, fixture_id: int):
        return self._get("/injuries", {"fixture": fixture_id})

    def statistics(self, fixture_id: int):
        return self._get("/fixtures/statistics", {"fixture": fixture_id})

    def standings(self, league_id: int, season: int):
        return self._get("/standings", {"league": league_id, "season": season})

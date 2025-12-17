import httpx
from typing import Any, Dict, Optional
from ..config import ODDS_API_KEY, ODDS_REGION, ODDS_MARKETS, ODDS_ODDS_FORMAT

class TheOddsAPI:
    BASE = "https://api.the-odds-api.com/v4"

    def __init__(self):
        self.key = ODDS_API_KEY
        self.client = httpx.Client(timeout=20.0)

    def close(self):
        self.client.close()

    def enabled(self) -> bool:
        return bool(self.key)

    def odds_soccer(self, sport_key: str, date_format: str = "iso") -> Dict[str, Any]:
        if not self.key:
            return {"enabled": False}
        url = f"{self.BASE}/sports/{sport_key}/odds"
        params = {
            "apiKey": self.key,
            "regions": ODDS_REGION,
            "markets": ODDS_MARKETS,
            "oddsFormat": ODDS_ODDS_FORMAT,
            "dateFormat": date_format,
        }
        r = self.client.get(url, params=params)
        r.raise_for_status()
        return {"enabled": True, "data": r.json()}

    def find_best_h2h(self, odds_payload: Dict[str, Any], home: str, away: str) -> Optional[Dict[str, Any]]:
        if not odds_payload.get("enabled"):
            return None
        for event in odds_payload.get("data", []):
            if event.get("home_team") == home and event.get("away_team") == away:
                return event
        return None

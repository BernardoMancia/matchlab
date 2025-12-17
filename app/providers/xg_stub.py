from typing import Dict, Any
from .xg_base import XGProvider

class XGStub(XGProvider):
    def enabled(self) -> bool:
        return False

    def get_match_xg_context(self, home: str, away: str, kickoff_iso: str) -> Dict[str, Any]:
        return {"enabled": False, "note": "xG provider não configurado. Plugin pronto para integrar uma fonte paga/privada."}

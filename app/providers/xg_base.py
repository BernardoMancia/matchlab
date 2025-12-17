from abc import ABC, abstractmethod
from typing import Dict, Any

class XGProvider(ABC):
    @abstractmethod
    def enabled(self) -> bool: ...

    @abstractmethod
    def get_match_xg_context(self, home: str, away: str, kickoff_iso: str) -> Dict[str, Any]:
        """Retorna contexto de xG. Se não tiver, retornar {"enabled": False}."""

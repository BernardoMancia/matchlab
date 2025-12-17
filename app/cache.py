import json
import time
from typing import Any, Optional
from .db import conn
from .config import CACHE_TTL_SECONDS

def cache_get(key: str) -> Optional[Any]:
    c = conn()
    row = c.execute("SELECT v, expires_at FROM cache WHERE k=?", (key,)).fetchone()
    c.close()
    if not row:
        return None
    if row["expires_at"] < int(time.time()):
        cache_del(key)
        return None
    return json.loads(row["v"])

def cache_set(key: str, value: Any, ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
    c = conn()
    expires = int(time.time()) + int(ttl_seconds)
    c.execute("INSERT OR REPLACE INTO cache(k,v,expires_at) VALUES(?,?,?)",
              (key, json.dumps(value, ensure_ascii=False), expires))
    c.commit()
    c.close()

def cache_del(key: str) -> None:
    c = conn()
    c.execute("DELETE FROM cache WHERE k=?", (key,))
    c.commit()
    c.close()

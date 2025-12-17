import sqlite3
from pathlib import Path
from .config import DB_PATH

def conn():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = conn()
    cur = c.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cache (
      k TEXT PRIMARY KEY,
      v TEXT NOT NULL,
      expires_at INTEGER NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS matches (
      fixture_id INTEGER PRIMARY KEY,
      league_id INTEGER,
      season INTEGER,
      kickoff_iso TEXT,
      home_name TEXT,
      away_name TEXT,
      home_id INTEGER,
      away_id INTEGER,
      status TEXT,
      home_goals INTEGER,
      away_goals INTEGER,
      raw_json TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      fixture_id INTEGER,
      created_at_iso TEXT,
      model TEXT,
      dossier_json TEXT,
      report_text TEXT,
      scoreline TEXT,
      confidence INTEGER,
      risk_json TEXT,
      FOREIGN KEY (fixture_id) REFERENCES matches(fixture_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS backtest_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at_iso TEXT,
      league_id INTEGER,
      season INTEGER,
      from_date TEXT,
      to_date TEXT,
      metrics_json TEXT
    )
    """)

    c.commit()
    c.close()

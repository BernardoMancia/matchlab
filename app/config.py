import os
from dotenv import load_dotenv

load_dotenv()

def env(key: str, default=None):
    return os.getenv(key, default)

OPENAI_API_KEY = env("OPENAI_API_KEY")
OPENAI_MODEL = env("OPENAI_MODEL", "gpt-5")

APIFOOTBALL_KEY = env("APIFOOTBALL_KEY")
APIFOOTBALL_BASE_URL = env("APIFOOTBALL_BASE_URL", "https://v3.football.api-sports.io")

APP_TZ = env("APP_TZ", "America/Sao_Paulo")
DB_PATH = env("DB_PATH", "./data/matchlab.sqlite")
CACHE_TTL_SECONDS = int(env("CACHE_TTL_SECONDS", "21600"))

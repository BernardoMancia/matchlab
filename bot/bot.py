import os
import re
import json
import base64
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Tuple, Dict, Any

import httpx
from openai import OpenAI

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# ========= Logging =========
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("matchlab-bot")

# ========= Env / Config =========
APP_TZ = os.getenv("APP_TZ", "America/Sao_Paulo")
TZ = ZoneInfo(APP_TZ)

APIFOOTBALL_KEY = os.getenv("APIFOOTBALL_KEY")
APIFOOTBALL_BASE_URL = os.getenv("APIFOOTBALL_BASE_URL", "https://v3.football.api-sports.io")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
API_BASE = os.getenv("MATCHLAB_API_BASE", "http://api:8000")

ASK_INPUT = 1

# Texto aceito:
# Time1 x Time2 - hh:mm - dd/mm/aaaa
TEXT_RX = re.compile(
    r"^\s*(?P<home>.+?)\s*[xX×]\s*(?P<away>.+?)\s*-\s*(?P<hm>\d{1,2}:\d{2})\s*-\s*(?P<dmy>\d{1,2}/\d{1,2}/\d{4})\s*$"
)

# ========= Helpers =========

def now_sp() -> datetime:
    return datetime.now(TZ)

def split_telegram(text: str, chunk_size: int = 3800):
    text = text or ""
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]

def parse_text_input(text: str) -> Optional[Tuple[str, str, datetime]]:
    m = TEXT_RX.match(text or "")
    if not m:
        return None
    home = m.group("home").strip()
    away = m.group("away").strip()
    hm = m.group("hm").strip()
    dmy = m.group("dmy").strip()

    kickoff = datetime.strptime(f"{dmy} {hm}", "%d/%m/%Y %H:%M").replace(tzinfo=TZ)
    return home, away, kickoff

async def apifootball_team_exists(team_name: str) -> bool:
    if not APIFOOTBALL_KEY:
        raise RuntimeError("APIFOOTBALL_KEY não definido no ambiente (.env).")

    async with httpx.AsyncClient(
        timeout=20.0,
        base_url=APIFOOTBALL_BASE_URL,
        headers={"x-apisports-key": APIFOOTBALL_KEY, "Accept": "application/json"},
    ) as c:
        r = await c.get("/teams", params={"search": team_name})
        r.raise_for_status()
        data = r.json()
        return bool(data.get("response"))

async def call_predict_api(home: str, away: str, kickoff_sp: datetime) -> Dict[str, Any]:
    payload = {
        "home": home,
        "away": away,
        "kickoff": kickoff_sp.strftime("%Y-%m-%d %H:%M"),
        "tz": APP_TZ,
        "season": kickoff_sp.year,
        "league_id": None,
        "recent_n": 5,
        "h2h_n": 10,
        "mode": "full",
    }

    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.post(f"{API_BASE}/predict", json=payload)
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}", "raw": r.text}
        return r.json()

def extract_json_safely(s: str) -> Optional[dict]:
    s = (s or "").strip()
    # tenta direto
    try:
        return json.loads(s)
    except Exception:
        pass
    # tenta achar um bloco JSON dentro do texto
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(s[start:end+1])
        except Exception:
            return None
    return None

async def extract_from_image_openai(image_bytes: bytes) -> dict:
    """
    Retorna:
      {"home": "...", "away": "...", "date_ddmmyyyy":"dd/mm/aaaa", "time_hhmm":"hh:mm"}
    ou:
      {"error":"NAO_DEU_CERTO"}
    """
    if not os.getenv("OPENAI_API_KEY"):
        return {"error": "NAO_DEU_CERTO"}

    client = OpenAI()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64}"

    prompt = (
        "Extraia os dados do jogo da imagem.\n"
        "Responda SOMENTE em JSON válido (sem texto extra) no formato EXATO:\n"
        '{"home":"...","away":"...","date_ddmmyyyy":"dd/mm/aaaa","time_hhmm":"hh:mm"}\n'
        "Regras:\n"
        "- Ignore odds, campeonato, textos extras.\n"
        "- Se não der para identificar com confiança, responda: {\"error\":\"NAO_DEU_CERTO\"}\n"
        "- Use dd/mm/aaaa e hh:mm."
    )

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            temperature=0.0,
        )
        txt = (resp.choices[0].message.content or "").strip()
        data = extract_json_safely(txt)
        if not data:
            return {"error": "NAO_DEU_CERTO"}
        return data
    except Exception as e:
        log.exception("Falha Vision OpenAI: %s", e)
        return {"error": "NAO_DEU_CERTO"}

def normalize_kickoff_from_image(data: dict) -> Optional[Tuple[str, str, datetime, str, str]]:
    home = (data.get("home") or "").strip()
    away = (data.get("away") or "").strip()
    dmy = (data.get("date_ddmmyyyy") or "").strip()
    hm = (data.get("time_hhmm") or "").strip()

    if not home or not away or not dmy or not hm:
        return None

    try:
        kickoff = datetime.strptime(f"{dmy} {hm}", "%d/%m/%Y %H:%M").replace(tzinfo=TZ)
    except Exception:
        return None

    return home, away, kickoff, dmy, hm

# ========= Telegram Handlers =========

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Use /prever para prever um jogo.\n"
        "Cancelamento: /cancelar"
    )

async def cmd_prever(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Envie a imagem com data e hora OU envie no formato:\n"
        "Time1 x Time2 - hh:mm - dd/mm/aaaa\n"
        "Ex: Flamengo x Palmeiras - 21:30 - 12/10/2025"
    )
    return ASK_INPUT

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    parsed = parse_text_input(text)

    if not parsed:
        await update.message.reply_text("Não deu certo. Use exatamente: Time1 x Time2 - hh:mm - dd/mm/aaaa")
        return ASK_INPUT

    home, away, kickoff = parsed

    if kickoff <= now_sp():
        await update.message.reply_text("Esse horário já passou (fuso São Paulo).")
        return ConversationHandler.END

    # valida times
    if not await apifootball_team_exists(home):
        await update.message.reply_text(f"Time não encontrado: {home}")
        return ConversationHandler.END
    if not await apifootball_team_exists(away):
        await update.message.reply_text(f"Time não encontrado: {away}")
        return ConversationHandler.END

    await update.message.reply_text("Analisando…")
    result = await call_predict_api(home, away, kickoff)

    if result.get("error"):
        await update.message.reply_text(f"Erro na API: {result.get('error')}\n{result.get('raw','')}")
        return ConversationHandler.END

    report = result.get("report") or json.dumps(result, ensure_ascii=False, indent=2)
    for part in split_telegram(report):
        await update.message.reply_text(part)

    return ConversationHandler.END

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    b = await file.download_as_bytearray()
    image_bytes = bytes(b)

    data = await extract_from_image_openai(image_bytes)
    norm = normalize_kickoff_from_image(data)

    if not norm:
        await update.message.reply_text(
            "Não deu certo extrair da imagem.\n"
            "Envie no formato: Time1 x Time2 - hh:mm - dd/mm/aaaa"
        )
        return ASK_INPUT

    home, away, kickoff, dmy, hm = norm

    if kickoff <= now_sp():
        await update.message.reply_text("Esse horário já passou (fuso São Paulo).")
        return ConversationHandler.END

    if not await apifootball_team_exists(home):
        await update.message.reply_text(f"Time não encontrado: {home}")
        return ConversationHandler.END
    if not await apifootball_team_exists(away):
        await update.message.reply_text(f"Time não encontrado: {away}")
        return ConversationHandler.END

    await update.message.reply_text(f"Entendi: {home} x {away} — {hm} — {dmy}\nAnalisando…")
    result = await call_predict_api(home, away, kickoff)

    if result.get("error"):
        await update.message.reply_text(f"Erro na API: {result.get('error')}\n{result.get('raw','')}")
        return ConversationHandler.END

    report = result.get("report") or json.dumps(result, ensure_ascii=False, indent=2)
    for part in split_telegram(report):
        await update.message.reply_text(part)

    return ConversationHandler.END

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelado.")
    return ConversationHandler.END

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Erro no bot: %s", context.error)

# ========= Main =========

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN não definido no ambiente (.env).")

    app = ApplicationBuilder().token(token).build()
    app.add_error_handler(on_error)

    conv = ConversationHandler(
        entry_points=[CommandHandler("prever", cmd_prever)],
        states={
            ASK_INPUT: [
                MessageHandler(filters.PHOTO, handle_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
            ]
        },
        fallbacks=[CommandHandler("cancelar", cmd_cancel)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(conv)

    log.info("Bot iniciado. Usar /prever.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

import os
import re
import json
import base64
from datetime import datetime
from zoneinfo import ZoneInfo

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

TZ = ZoneInfo(os.getenv("APP_TZ", "America/Sao_Paulo"))
APIFOOTBALL_KEY = os.getenv("APIFOOTBALL_KEY")
APIFOOTBALL_BASE_URL = os.getenv("APIFOOTBALL_BASE_URL", "https://v3.football.api-sports.io")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

API_BASE = os.getenv("MATCHLAB_API_BASE", "http://api:8000")

ASK_INPUT = 1

RX = re.compile(
    r"^\s*(?P<home>.+?)\s*[xX×]\s*(?P<away>.+?)\s*-\s*(?P<hm>\d{1,2}:\d{2})\s*-\s*(?P<dmy>\d{1,2}/\d{1,2}/\d{4})\s*$"
)

def now_sp() -> datetime:
    return datetime.now(TZ)

def parse_text_line(text: str):
    m = RX.match(text or "")
    if not m:
        return None
    home = m.group("home").strip()
    away = m.group("away").strip()
    hm = m.group("hm")
    dmy = m.group("dmy")
    dt = datetime.strptime(f"{dmy} {hm}", "%d/%m/%Y %H:%M").replace(tzinfo=TZ)
    return home, away, dt

async def apifootball_team_exists(team_name: str) -> bool:
    if not APIFOOTBALL_KEY:
        raise RuntimeError("APIFOOTBALL_KEY não definido no ambiente.")
    async with httpx.AsyncClient(
        timeout=20.0,
        base_url=APIFOOTBALL_BASE_URL,
        headers={"x-apisports-key": APIFOOTBALL_KEY, "Accept": "application/json"},
    ) as c:
        r = await c.get("/teams", params={"search": team_name})
        r.raise_for_status()
        data = r.json()
        return bool(data.get("response"))

async def extract_from_image_openai(image_bytes: bytes) -> dict:
    client = OpenAI()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64}"

    prompt = (
        "Extraia os dados do jogo da imagem.\n"
        "Responda SOMENTE em JSON válido, sem texto extra, no formato:\n"
        '{"home":"...","away":"...","date_ddmmyyyy":"dd/mm/aaaa","time_hhmm":"hh:mm"}\n'
        "Se não conseguir, responda:\n"
        '{"error":"NAO_DEU_CERTO"}'
    )

    resp = client.responses.create(
        model=OPENAI_MODEL,
        reasoning={"effort": "low"},
        input=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "input_image", "image_url": data_url},
            ]
        }]
    )

    txt = resp.output_text.strip()
    try:
        return json.loads(txt)
    except Exception:
        return {"error": "NAO_DEU_CERTO"}

async def call_matchlab_predict(home: str, away: str, kickoff_sp: datetime) -> str:
    payload = {
        "home": home,
        "away": away,
        "kickoff": kickoff_sp.strftime("%Y-%m-%d %H:%M"),
        "tz": "America/Sao_Paulo",
        "season": kickoff_sp.year,
        "league_id": None,
        "recent_n": 5,
        "h2h_n": 10,
        "mode": "full"
    }

    async with httpx.AsyncClient(timeout=90.0) as c:
        r = await c.post(f"{API_BASE}/predict", json=payload)
        if r.status_code != 200:
            return f"Falhou ao prever (HTTP {r.status_code}):\n{r.text}"
        data = r.json()
        return data.get("report") or json.dumps(data, ensure_ascii=False, indent=2)

async def start_prever(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Envie a imagem com data e hora OU diga:\n"
        "Time1 x Time2 - hora:minuto - dia/mês/ano\n"
        "Ex: Fenerbahce x Konyaspor - 14:00 - 15/12/2025"
    )
    return ASK_INPUT

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    parsed = parse_text_line(text)
    if not parsed:
        await update.message.reply_text("Não deu certo. Use exatamente: Time1 x Time2 - hh:mm - dd/mm/aaaa")
        return ASK_INPUT

    home, away, kickoff = parsed

    if kickoff <= now_sp():
        await update.message.reply_text("Esse horário já passou (fuso São Paulo).")
        return ConversationHandler.END

    if not await apifootball_team_exists(home):
        await update.message.reply_text(f"Time não encontrado: {home}")
        return ConversationHandler.END
    if not await apifootball_team_exists(away):
        await update.message.reply_text(f"Time não encontrado: {away}")
        return ConversationHandler.END

    await update.message.reply_text("Analisando…")
    report = await call_matchlab_predict(home, away, kickoff)
    await update.message.reply_text(report[:3900])
    if len(report) > 3900:
        await update.message.reply_text(report[3900:7800])
    return ConversationHandler.END

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    b = await file.download_as_bytearray()
    image_bytes = bytes(b)

    data = await extract_from_image_openai(image_bytes)
    if data.get("error"):
        await update.message.reply_text("Não deu certo extrair da imagem. Envie no formato: Time1 x Time2 - hh:mm - dd/mm/aaaa")
        return ASK_INPUT

    home = (data.get("home") or "").strip()
    away = (data.get("away") or "").strip()
    dmy = (data.get("date_ddmmyyyy") or "").strip()
    hm = (data.get("time_hhmm") or "").strip()

    try:
        kickoff = datetime.strptime(f"{dmy} {hm}", "%d/%m/%Y %H:%M").replace(tzinfo=TZ)
    except Exception:
        await update.message.reply_text("Não deu certo interpretar data/hora da imagem. Tente outra imagem ou envie texto no formato correto.")
        return ASK_INPUT

    if kickoff <= now_sp():
        await update.message.reply_text("Esse horário já passou (fuso São Paulo).")
        return ConversationHandler.END

    if not home or not away:
        await update.message.reply_text("Não deu certo pegar os nomes dos times na imagem.")
        return ASK_INPUT

    if not await apifootball_team_exists(home):
        await update.message.reply_text(f"Time não encontrado: {home}")
        return ConversationHandler.END
    if not await apifootball_team_exists(away):
        await update.message.reply_text(f"Time não encontrado: {away}")
        return ConversationHandler.END

    await update.message.reply_text(f"Entendi: {home} x {away} — {hm} — {dmy}\nAnalisando…")
    report = await call_matchlab_predict(home, away, kickoff)
    await update.message.reply_text(report[:3900])
    if len(report) > 3900:
        await update.message.reply_text(report[3900:7800])
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelado.")
    return ConversationHandler.END

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN não definido.")

    app = ApplicationBuilder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("prever", start_prever)],
        states={
            ASK_INPUT: [
                MessageHandler(filters.PHOTO, handle_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
            ]
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
    )

    app.add_handler(conv)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

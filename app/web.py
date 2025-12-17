from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "result": None, "error": None})

@router.post("/prever", response_class=HTMLResponse)
def prever_form(
    request: Request,
    home: str = Form(...),
    away: str = Form(...),
    kickoff: str = Form(...),
    season: int = Form(...),
):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "result": {"home": home, "away": away, "kickoff": kickoff, "season": season}, "error": None},
    )

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi import APIRouter
from app.core.config import templates

router = APIRouter(tags=["pages"])

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})
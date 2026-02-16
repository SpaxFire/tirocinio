from typing import Annotated
from fastapi import Request, Header, APIRouter
from fastapi.responses import HTMLResponse
from app.core.config import templates

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    hx_request: Annotated[str | None, Header()] = None
):
    """
    Home page:
    - se richiesta HTMX → solo contenuto centrale
    - se richiesta normale → pagina completa
    """
    if hx_request:
        return templates.TemplateResponse(
            "partials/home_content.html",
            {"request": request}
        )

    return templates.TemplateResponse(
        "home.html",
        {"request": request}
    )


@router.get("/empty", response_class=HTMLResponse)
async def empty():
    """
    Endpoint vuoto usato per svuotare i messaggi di errore nei modali tramite HTMX
    """
    return HTMLResponse("")

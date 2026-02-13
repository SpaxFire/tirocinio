from typing import Annotated, Union
from fastapi import Request, Header, APIRouter
from fastapi.responses import HTMLResponse
from app.core.render import render

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    hx_request: Annotated[str | None, Header()] = None
):
    # richiesta HTMX → solo contenuto centrale
    if hx_request:
        return await render(
            request,
            "partials/home_content.html"
        )

    # richiesta normale → pagina completa
    return await render(
        request,
        "home.html"
    )

@router.get("/empty")
async def empty():
    return HTMLResponse("")
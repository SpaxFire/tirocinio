from http.client import HTTPException
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.db.init_db import init_db
from app.core.config import templates

init_db()

from app.api.router import api_router

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(api_router)

@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc: HTTPException):

    # se è richiesta HTMX → mostra modal login
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "auth/login_modal.html",
            {"request": request},
            status_code=200
        )

    return HTMLResponse("Unauthorized", status_code=401)
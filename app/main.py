from http.client import HTTPException
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.db.init_db import init_db
from app.core.config import templates

#init_db()

from app.api.router import api_router

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(api_router)

# Gestione errori 401 per HTMX (utente non autenticato)
@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc: HTTPException):

    if request.headers.get("HX-Request"):
        response = templates.TemplateResponse(
            "auth/login_modal.html",
            {"request": request},
            status_code=200,
        )
        response.headers["HX-Retarget"] = "#modal-container"
        response.headers["HX-Reswap"] = "innerHTML"
        return response

    return HTMLResponse("Unauthorized", status_code=401)
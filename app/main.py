from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import templates
from app.core.security import optional_current_user_cookie
from app.api.router import api_router
from app.services.audit_blockchain import AuditBlockchain

# Inizializziamo la blockchain di audit e la app FastAPI
app = FastAPI()
audit_blockchain = AuditBlockchain()

# Middleware per gestire l'utente corrente e registrare gli eventi nella blockchain di audit
class CurrentUserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        access_token = request.cookies.get("access_token")
        user = await optional_current_user_cookie(access_token)

        request.state.user = user

        response = await call_next(request)
        
        # Rimuoviamo il cookie flash_message dopo averlo letto da request.cookies
        # request.cookies contains i cookie inviati dal client, mentre response.delete_cookie rimuove il cookie dalla risposta HTTP inviata al client.
        if request.cookies.get("flash_message"):
            response.delete_cookie("flash_message")

        audit_payload = { # payload dell'evento di audit
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "user": getattr(user, "username", None),
            "query_params": dict(request.query_params),
        }

        event_type = f"{request.method.lower()}_request" # tipo di evento basato sul metodo HTTP
        audit_blockchain.append_event(event_type, audit_payload)
        return response

# Aggiungiamo il middleware alla app FastAPI
app.add_middleware(CurrentUserMiddleware)


# STATIC
app.mount("/static", StaticFiles(directory="static"), name="static")

# ROUTER
app.include_router(api_router)


# RENDIAMO current_user GLOBALE NEI TEMPLATE
templates.env.globals["current_user"] = lambda request: request.state.user


# Gestione errori 401 per HTMX
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
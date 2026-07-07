import asyncio
import logging
import os

from app.core.env import load_app_env

load_app_env()

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.router import api_router
from app.core.config import templates
from app.core.security import optional_current_user_cookie
from app.services.audit_blockchain import AuditBlockchain
from app.services.audit_client import AuditServiceClient
from app.services.mqtt_client import mqtt_notification_client
from app.services.pending_queue import PendingAuditQueue

# Configuriamo il logger scrivendo i messaggi di log su stdout con un formato specifico
logger = logging.getLogger("audit")

# Inizializziamo la blockchain di audit e le app FastAPI (servizio principale, servizio di audit)
app = FastAPI()
audit_blockchain = AuditBlockchain()

# Inizializziamo il client di audit e la coda pendente
audit_client = AuditServiceClient()
pending_queue = PendingAuditQueue()

# Middleware per gestire l'utente corrente e registrare gli eventi nella blockchain di audit
class CurrentUserMiddleware(BaseHTTPMiddleware):

    # Il metodo del middleware che viene eseguito per ogni richiesta HTTP prima che arrivi alla route e dopo che la route ha prodotto la risposta. 
    # In pratica è il punto in cui puoi intercettare la richiesta
    async def dispatch(self, request: Request, call_next):
        access_token = request.cookies.get("access_token")
        user = await optional_current_user_cookie(access_token)

        request.state.user = user

        response = await call_next(request) # Chiama la route successiva e ottiene la risposta.
        
        # Nella stessa risposta il server ordina la cancellazione con response.delete_cookie
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
        # Se il servizio di audit è abilitato, creiamo la transazione firmata e la inviamo al validator remoto.
        # In caso di fallimento, la transazione finisce nella coda pendente e verrà ritentata.
        # Se il servizio non è configurato, scriviamo direttamente nella blockchain locale.
        if audit_client.enabled:
            transaction = audit_blockchain.create_transaction(event_type, audit_payload)
            sent = await audit_client.append_transaction(transaction)
            if not sent:
                # Se l'invio fallisce, mettiamo l'evento in coda per il retry
                pending_queue.push(event_type, audit_payload)
                logger.warning(
                    "[AUDIT] Validator configurato ma non raggiungibile (%s) — evento %s %s accodato (coda: %d)",
                    audit_client.validator_url,
                    request.method,
                    request.url.path,
                    len(pending_queue._load()),
                )
            else:
                # La transazione è stata accettata dal validator (e dalla sua firma verificata)
                logger.debug(
                    "[AUDIT] Transazione firmata inviata e verificata dal validator: %s %s (status %s)",
                    request.method, request.url.path, response.status_code,
                )
        else:
            # Se il validator non è configurato, accodiamo l'evento su disco per ritentare più tardi
            pending_queue.push(event_type, audit_payload)
            logger.debug(
                "[AUDIT] Validator non configurato nel processo (AUDIT_VALIDATOR_URL vuota) — evento accodato in locale: %s %s",
                request.method,
                request.url.path,
            )
        return response

# Aggiungiamo il middleware alla app FastAPI
app.add_middleware(CurrentUserMiddleware)

# Funzione per inviare al validator tutti gli eventi nella coda pendente.
# A differenza di dispatch, questa funzione non è un middleware ma un task in background che viene eseguito periodicamente.
async def _flush_pending_events_once() -> None:
    """Tenta di inviare al validator tutti gli eventi nella coda pendente.
    Gli eventi che falliscono vengono rimessi in coda."""
    if not audit_client.enabled or pending_queue.is_empty():
        return
    events = pending_queue.pop_all()
    logger.info("[AUDIT] Flush: tentativo di invio di %d eventi pendenti al validator", len(events))
    failed: list = []
    for event in events:
        # Ricrea la transazione durante il retry (avrà timestamp differente)
        transaction = audit_blockchain.create_transaction(event["event_type"], event["payload"])
        sent = await audit_client.append_transaction(transaction)
        if not sent:
            failed.append(event)
    sent_count = len(events) - len(failed)
    if sent_count:
        logger.info("[AUDIT] Flush completato: %d eventi inviati al validator", sent_count)
    # Se alcuni eventi falliscono ancora, li rimettiamo in coda
    if failed:
        for event in failed:
            pending_queue.push(event["event_type"], event["payload"])
        logger.warning(
            "[AUDIT] Flush parziale: %d eventi rimessi in coda (validator ancora non raggiungibile)",
            len(failed),
        )

# Creiamo un task in background che ogni `interval_seconds` chiama `_flush_pending_events_once`.
async def _flush_pending_events(interval_seconds: int = 30) -> None:
    """Task in background: ogni `interval_seconds` chiama _flush_pending_events_once."""
    while True:
        await asyncio.sleep(interval_seconds)
        await _flush_pending_events_once()


# Eventi di startup dell'applicazione
@app.on_event("startup")
async def startup_event() -> None:
    log_level_name = os.getenv("APP_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    if audit_client.enabled:
        logger.info("[AUDIT] Validator remoto configurato nel processo: %s", audit_client.validator_url)
        if await audit_client.is_reachable():
            logger.info("[AUDIT] Validator remoto raggiunto con successo: %s", audit_client.validator_url)
        else:
            logger.warning("[AUDIT] Validator remoto configurato ma non raggiungibile all'avvio: %s", audit_client.validator_url)
    else:
        logger.info("[AUDIT] Validator remoto non configurato nel processo (AUDIT_VALIDATOR_URL vuota) — modalità coda locale persistente")
    asyncio.create_task(_flush_pending_events()) # Task in background per inviare periodicamente gli eventi pendenti al validator remoto
    mqtt_notification_client.attach_loop(asyncio.get_running_loop())
    mqtt_notification_client.start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    mqtt_notification_client.stop()


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
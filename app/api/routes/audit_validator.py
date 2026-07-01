import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.audit_blockchain import AuditBlockchain

router = APIRouter(prefix="/internal/audit", tags=["audit-validator"])
audit_blockchain = AuditBlockchain()
logger = logging.getLogger("audit")

# Route per la gestione degli eventi di audit e della catena di audit. 
# Queste route sono utilizzate dal servizio di audit esterno per interagire con il server.
class AuditEventRequest(BaseModel):
    event_type: str
    payload: dict[str, Any]


# Route per la verifica dello stato del servizio di audit esterno (usato per debug e monitoraggio)
@router.get("/health")
async def healthcheck() -> dict[str, str]:
    logger.info("[AUDIT] Validator healthcheck ricevuto")
    return {"status": "ok"}

# Route per l'aggiunta di un evento di audit alla catena di audit
@router.post("/events")
async def append_event(event: AuditEventRequest) -> dict[str, Any]:
    transaction = audit_blockchain.append_event(event.event_type, event.payload)
    logger.info("[AUDIT] Validator ha salvato evento %s", event.event_type)
    return {"ok": True, "transaction": transaction}


# Route per ottenere la vista della catena di audit
@router.get("/chain")
async def get_chain(
    user: str | None = None,
    event_type: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    logger.debug("[AUDIT] Validator chain request filtrata")
    chain = getattr(audit_blockchain, "chain", {"chain": []})
    filtered_chain = audit_blockchain.filter_chain(
        user=user,
        event_type=event_type,
        start_time=start_time,
        end_time=end_time,
    )
    return {
        "chain": {**chain, "chain": filtered_chain},
        "is_valid": audit_blockchain.validate_chain(),
    }

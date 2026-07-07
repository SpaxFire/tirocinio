import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.audit_blockchain import AuditBlockchain

router = APIRouter(prefix="/internal/audit", tags=["audit-validator"])
audit_blockchain = AuditBlockchain()
logger = logging.getLogger("audit")

# Schema per ricevere una transazione firmata dal server
class SignedTransactionRequest(BaseModel):
    event_type: str
    payload: dict[str, Any]
    timestamp: str
    server_id: str
    signature: str


# Route per la gestione degli eventi di audit e della catena di audit. 
# Queste route sono utilizzate dal servizio di audit esterno per interagire con il server.


# Route per la verifica dello stato del servizio di audit esterno (usato per debug e monitoraggio)
@router.get("/health")
async def healthcheck() -> dict[str, str]:
    logger.info("[AUDIT] Validator healthcheck ricevuto")
    return {"status": "ok"}

# Route per ricevere una transazione firmata dal server, verificarla e creare il blocco
@router.post("/transactions")
async def append_transaction(tx: SignedTransactionRequest) -> dict[str, Any]:
    """Riceve una transazione firmata dal server.
    1. Verifica la firma della transazione
    2. Crea il blocco dalla transazione
    3. Firma il blocco e lo accoda
    """
    tx_dict = tx.model_dump()
    
    # Step 1: Verifica la firma della transazione
    if not audit_blockchain.verify_transaction(tx_dict):
        logger.warning(
            "[AUDIT] Rifiutata transazione con firma non valida: evento %s",
            tx.event_type,
        )
        return {"ok": False, "error": "Invalid transaction signature"}
    
    # Step 2: Crea il blocco dalla transazione verificata
    # (il validatore è l'autorità PoA che crea i blocchi)
    block = audit_blockchain.create_block(
        event_type=tx_dict["event_type"],
        payload=tx_dict["payload"],
        timestamp=tx_dict["timestamp"],
    )
    
    # Step 3: Accoda il blocco alla catena
    audit_blockchain.chain["chain"].append(block)
    audit_blockchain._save_chain()
    
    logger.info(
        "[AUDIT] Validator ha verificato e bloccato transazione: evento %s (index %d, signature valida)",
        tx.event_type,
        block["index"],
    )
    return {"ok": True, "block": block}


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
    filtered_chain.reverse()
    is_valid = audit_blockchain.validate_chain()
    logger.info(
        "[AUDIT] Validator chain response: is_valid=%s filtered_blocks=%d total_blocks=%d",
        is_valid,
        len(filtered_chain),
        len(chain.get("chain", [])) if isinstance(chain, dict) else 0,
    )
    return {
        "chain": {**chain, "chain": filtered_chain},
        "is_valid": is_valid,
    }

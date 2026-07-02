import logging
import os
from typing import Any

import httpx

# Configuriamo il logger per il servizio di audit
logger = logging.getLogger("audit")

# Classe client per interagire con il servizio di audit esterno
# Prende le richieste del cliente (arrivate al server) e le inoltra al servizio di audit esterno.
# Viene chiamato da main.py (punto di ingresso del server).
class AuditServiceClient:
    # Inizializza il client con l'URL del validator e il timeout per le richieste HTTP
    def __init__(self, validator_url: str | None = None, timeout_seconds: float = 2.0):
        self._explicit_url = validator_url  # solo se passato esplicitamente
        self.timeout_seconds = timeout_seconds

    # Proprietà dinamica: riletta da os.environ ad ogni accesso, così funziona
    # anche se la variabile viene caricata dal .env dopo la creazione dell'istanza.
    @property
    def validator_url(self) -> str:
        url = self._explicit_url or os.getenv("AUDIT_VALIDATOR_URL", "")
        return url.rstrip("/")

    # Proprietà per verificare se il servizio di audit esterno è abilitato (se l'URL del validator è configurato)
    @property
    def enabled(self) -> bool:
        return bool(self.validator_url)
    
    # Metodo privato per inviare dati al validator con error handling
    async def _post_to_validator(self, endpoint: str, data: dict[str, Any]) -> bool:
        """Invia dati al validator tramite POST."""
        if not self.enabled:
            return False
        full_endpoint = f"{self.validator_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(full_endpoint, json=data)
                response.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.warning("[AUDIT] Connessione al validator fallita (%s): %s", full_endpoint, exc)
            return False
    
    # Funzione per inviare una transazione firmata dal server al validatore
    async def append_transaction(self, transaction: dict[str, Any]) -> bool:
        """Invia una transazione firmata al validatore per la verifica e creazione del blocco."""
        return await self._post_to_validator(
            "/internal/audit/transactions",
            transaction,
        )

    # Funzione per inviare un blocco firmato al servizio esterno con verifica della firma
    async def append_signed_block(self, block: dict[str, Any]) -> bool:
        """Invia un blocco firmato al validatore. La firma viene verificata dal validatore."""
        return await self._post_to_validator(
            "/internal/audit/blocks",
            block,
        )
    
    # Funzione per verificare se il servizio di audit esterno è raggiungibile (chiamando l'endpoint di healthcheck)
    async def is_reachable(self) -> bool:
        if not self.enabled:
            return False

        endpoint = f"{self.validator_url}/internal/audit/health"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(endpoint)
                response.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.warning("[AUDIT] Validator non raggiungibile (%s): %s", endpoint, exc)
            return False

    # Funzione per ottenere la vista della catena di audit dal servizio esterno
    async def get_chain_view(
        self,
        *,
        user: str | None = None,
        event_type: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            logger.info("[AUDIT] get_chain_view saltata: validator non configurato")
            return None

        # Costruiamo l'endpoint per ottenere la vista della catena di audit dal servizio esterno
        endpoint = f"{self.validator_url}/internal/audit/chain"
        params = {
            "user": user,
            "event_type": event_type,
            "start_time": start_time,
            "end_time": end_time,
        }
        # Mandiamo la richiesta al servizio esterno per ottenere la vista della catena di audit e gestiamo eventuali errori
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(endpoint, params=params)
                response.raise_for_status()
                payload = response.json()
            logger.info(
                "[AUDIT] get_chain_view OK: endpoint=%s status=%s",
                endpoint,
                response.status_code,
            )
            if not isinstance(payload, dict):
                logger.warning("[AUDIT] get_chain_view payload non-dict: %s", type(payload).__name__)
                return None
            logger.debug("[AUDIT] get_chain_view keys payload: %s", list(payload.keys()))
            return payload
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[AUDIT] Errore durante il recupero della vista della catena di audit (%s): %s", endpoint, exc)
            return None

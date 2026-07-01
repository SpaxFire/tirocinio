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
    
    # Funzione per inviare un evento di audit al servizio esterno
    async def append_event(self, event_type: str, payload: dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        # Costruiamo l'endpoint per inviare l'evento di audit al servizio esterno
        endpoint = f"{self.validator_url}/internal/audit/events"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    endpoint,
                    json={"event_type": event_type, "payload": payload},
                )
                response.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.warning("[AUDIT] Connessione al validator fallita (%s): %s", endpoint, exc)
            return False
    
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
            if not isinstance(payload, dict):
                return None
            return payload
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[AUDIT] Errore durante il recupero della vista della catena di audit (%s): %s", endpoint, exc)
            return None

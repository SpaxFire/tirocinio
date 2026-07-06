import json
import os
from pathlib import Path
from typing import Any


class PendingAuditQueue:
    """Coda persistente di eventi di audit non ancora consegnati al validator remoto.

    Gli eventi vengono scritti su file JSON quando il validator è irraggiungibile
    e rimossi dopo che il flush al validator va a buon fine.
    """

    def __init__(self, queue_path: str | Path | None = None):
        self.queue_path = Path(
            queue_path or os.getenv("AUDIT_PENDING_PATH", "data/pending_audit_events.json")
        )
        self.queue_path.parent.mkdir(parents=True, exist_ok=True) # Crea la directory se non esiste

    def push(self, event_type: str, payload: dict[str, Any]) -> None:
        """Aggiunge un evento alla coda persistente."""
        events = self._load()
        events.append({"event_type": event_type, "payload": payload})
        self._save(events)

    def pop_all(self) -> list[dict[str, Any]]:
        """Restituisce tutti gli eventi pendenti e svuota la coda."""
        events = self._load()
        if events:
            self._save([])
        return events

    def is_empty(self) -> bool:
        return len(self._load()) == 0

    def _load(self) -> list[dict[str, Any]]:
        if not self.queue_path.exists():
            return []
        with self.queue_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []

    def _save(self, events: list[dict[str, Any]]) -> None:
        with self.queue_path.open("w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
            f.write("\n")

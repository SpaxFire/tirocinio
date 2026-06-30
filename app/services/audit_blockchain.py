import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# classe AuditBlockchain per la gestione della blockchain di audit
class AuditBlockchain:

    # Inizializza la classe AuditBlockchain con il percorso della catena e il segreto di firma.
    def __init__(self, chain_path: str | Path | None = None, signing_secret: str | None = None):
        self.chain_path = Path(chain_path or os.getenv("AUDIT_CHAIN_PATH", "data/audit_chain.json"))
        self.signing_secret = signing_secret or os.getenv("AUDIT_SIGNING_SECRET", "fastapi-audit-secret")
        self.chain_path.parent.mkdir(parents=True, exist_ok=True)
        self.chain = self._load_chain()

    # Carica la blockchain di audit da un file JSON. Se il file non esiste, crea un blocco genesi e salva la catena.
    def _load_chain(self) -> dict[str, Any]:
        if not self.chain_path.exists():
            genesis_block = self._build_block(
                index=0,
                event_type="genesis",
                payload={"message": "Initial audit chain"},
                previous_hash="0",
            )
            chain = {"validator": "fastapi-poa-node", "chain": [genesis_block]}
            self._save_chain(chain)
            return chain

        with self.chain_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        if not isinstance(data, dict) or "chain" not in data:
            raise ValueError("Audit chain file has an invalid structure")

        return data


    # Salva la blockchain di audit su un file JSON.
    def _save_chain(self, chain: dict[str, Any] | None = None) -> None:
        payload = chain or self.chain
        with self.chain_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    
    # Restituisce una rappresentazione JSON canonica di un valore, ordinando le chiavi e rimuovendo gli spazi bianchi superflui.
    def _canonical_json(self, value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    # Calcola l'hash SHA-256 di un payload.
    def _hash_payload(self, payload: dict[str, Any]) -> str:
        return hashlib.sha256(self._canonical_json(payload).encode("utf-8")).hexdigest()

    # Firma un payload utilizzando HMAC con SHA-256.
    def _sign_payload(self, payload: dict[str, Any]) -> str:
        return hmac.new(
            self.signing_secret.encode("utf-8"),
            self._canonical_json(payload).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    
    # Costruisce un blocco della blockchain di audit con i campi richiesti, calcola l'hash e la firma del blocco.
    def _build_block(
        self,
        *,
        index: int,
        event_type: str,
        payload: dict[str, Any],
        previous_hash: str,
    ) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        block = {
            "index": index,
            "timestamp": timestamp,
            "event_type": event_type,
            "payload": payload,
            "validator": "fastapi-poa-node",
            "previous_hash": previous_hash,
        }
        block["hash"] = self._hash_payload(block)
        block["signature"] = self._sign_payload({"hash": block["hash"], "validator": block["validator"]})
        return block

    # Crea una nuova transazione (blocco) nella blockchain di audit con il tipo di evento e il payload forniti.
    def create_transaction(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        previous_hash = self.chain["chain"][-1]["hash"] if self.chain.get("chain") else "0"
        return self._build_block(
            index=len(self.chain["chain"]),
            event_type=event_type,
            payload=payload,
            previous_hash=previous_hash,
        )

    # Aggiunge un evento alla blockchain di audit, creando una nuova transazione e salvando la catena.
    def append_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        transaction = self.create_transaction(event_type, payload)
        self.chain["chain"].append(transaction)
        self._save_chain(self.chain)
        return transaction

    # Valida una transazione della blockchain di audit.
    def validate_transaction(self, transaction: dict[str, Any]) -> bool:
        required_fields = {"index", "timestamp", "event_type", "payload", "validator", "previous_hash", "hash", "signature"}
        if not required_fields.issubset(transaction.keys()):
            return False

        if transaction.get("validator") != "fastapi-poa-node":
            return False

        hash_payload = {
            "index": transaction["index"],
            "timestamp": transaction["timestamp"],
            "event_type": transaction["event_type"],
            "payload": transaction["payload"],
            "validator": transaction["validator"],
            "previous_hash": transaction["previous_hash"],
        }

        if transaction.get("hash") != self._hash_payload(hash_payload):
            return False

        expected_signature = self._sign_payload({"hash": transaction["hash"], "validator": transaction["validator"]})
        return hmac.compare_digest(transaction.get("signature", ""), expected_signature)

    # Filtra la catena di audit in base a utente, tipo di evento e intervallo temporale.
    def filter_chain(
        self,
        *,
        user: str | None = None,
        event_type: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> list[dict[str, Any]]:
        def _parse_time(value: str | None):
            if not value:
                return None
            if isinstance(value, datetime):
                return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None

        start_dt = _parse_time(start_time)
        end_dt = _parse_time(end_time)
        filtered_blocks: list[dict[str, Any]] = []

        for block in self.chain.get("chain", []):
            payload = block.get("payload") or {}
            block_user = payload.get("user")
            block_event_type = block.get("event_type")
            block_timestamp = block.get("timestamp")
            block_dt = _parse_time(block_timestamp)

            if user and block_user != user:
                continue
            if event_type and block_event_type != event_type:
                continue
            if start_dt and block_dt and block_dt < start_dt:
                continue
            if end_dt and block_dt and block_dt > end_dt:
                continue

            filtered_blocks.append(block)

        return filtered_blocks

    # Valida l'intera catena della blockchain di audit.
    def validate_chain(self) -> bool:
        chain = self.chain.get("chain", [])
        if not chain:
            return False

        expected_previous_hash = "0" # hash del blocco genesi

        # Validiamo ogni blocco della catena, controllando la firma, l'indice e l'hash del blocco precedente.
        for index, block in enumerate(chain):
            if not self.validate_transaction(block):
                return False
            if block.get("index") != index:
                return False
            if index > 0 and block.get("previous_hash") != expected_previous_hash:
                return False
            expected_previous_hash = block.get("hash", "")

        return True

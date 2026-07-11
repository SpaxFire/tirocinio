import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("audit")


class AuditTransactionSigner:

    # Signer dedicato al backend: firma solo le transazioni server -> validator.
    # Non carica/salva chain e non usa il segreto di firma dei blocchi.
    def __init__(
        self,
        transaction_signing_secret: str | None = None,
        signing_secret: str | None = None,
    ):
        legacy_secret = signing_secret or os.getenv("AUDIT_SIGNING_SECRET")
        self.transaction_signing_secret = (
            transaction_signing_secret
            or os.getenv("AUDIT_TX_SIGNING_SECRET")
            or legacy_secret
            or "fastapi-audit-tx-secret"
        )

    def _canonical_json(self, value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _sign_payload(self, payload: dict[str, Any]) -> str:
        return hmac.new(
            self.transaction_signing_secret.encode("utf-8"),
            self._canonical_json(payload).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def create_transaction(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        transaction = {
            "event_type": event_type,
            "payload": payload,
            "timestamp": timestamp,
            "server_id": "fastapi-server",
        }
        transaction["signature"] = self._sign_payload(transaction)
        return transaction

# classe AuditBlockchain per la gestione della blockchain di audit
class AuditBlockchain:

    # Inizializza la classe AuditBlockchain con il percorso della catena e il segreto di firma.
    def __init__(
        self,
        chain_path: str | Path | None = None,
        signing_secret: str | None = None,             # Segreto di firma legacy (stesso per validatore e server)
        transaction_signing_secret: str | None = None, # Segreto di firma per le transazioni (server)
        block_signing_secret: str | None = None,       # Segreto di firma per i blocchi (validatore)
    ):
        self.chain_path = Path(chain_path or os.getenv("AUDIT_CHAIN_PATH", "data/audit_chain.json"))
        legacy_secret = signing_secret or os.getenv("AUDIT_SIGNING_SECRET")
        self.transaction_signing_secret = (
            transaction_signing_secret
            or os.getenv("AUDIT_TX_SIGNING_SECRET")
            or legacy_secret
            or "fastapi-audit-tx-secret"  # segrerto di default per le transazioni (server)
        )
        self.block_signing_secret = (
            block_signing_secret
            or os.getenv("AUDIT_BLOCK_SIGNING_SECRET")
            or legacy_secret
            or "fastapi-audit-block-secret"  # segreto di default per i blocchi (validatore)
        )
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
        
        # Carica la catena di audit da un file JSON e verifica la sua struttura.
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

    # Firma un payload utilizzando HMAC con SHA-256 e il segreto fornito.
    def _sign_payload(self, payload: dict[str, Any], *, secret: str) -> str:
        return hmac.new(
            secret.encode("utf-8"),                        # Chiave segreta per la firma
            self._canonical_json(payload).encode("utf-8"), # Dati da firmare (payload in formato JSON canonico)
            hashlib.sha256,                                # Algoritmo di hash da utilizzare per HMAC
        ).hexdigest()
    
    # Costruisce un blocco della blockchain di audit con i campi richiesti, calcola l'hash e la firma del blocco.
    # Processo PoA: 1) crea blocco base 2) calcola SHA256(blocco_base) 3) firma il risultato 4) accoda
    def _build_block(
        self,
        *,
        index: int,
        event_type: str,
        payload: dict[str, Any],
        previous_hash: str,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        # Step 1: Crea il blocco base (senza hash e firma)
        block = {
            "index": index,
            "timestamp": timestamp,
            "event_type": event_type,
            "payload": payload,
            "validator": "fastapi-poa-node",
            "previous_hash": previous_hash,
        }
        # Step 2: Calcola SHA256 del blocco base
        block["hash"] = self._hash_payload(block)
        
        # Step 3: Firma il risultato SHA256 (l'hash del blocco)
        # La firma è HMAC-SHA256 del hash + validator
        block["signature"] = self._sign_payload(
            {"hash": block["hash"], "validator": block["validator"]},
            secret=self.block_signing_secret,
        )
        
        return block

    # Crea una transazione firmata (usato dal server).
    # Una transazione è un evento che il server invia al validatore.
    def create_transaction(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Crea una transazione firmata dal server. Il validatore poi ne creerà un blocco."""
        timestamp = datetime.now(timezone.utc).isoformat()
        transaction = {
            "event_type": event_type,
            "payload": payload,
            "timestamp": timestamp,
            "server_id": "fastapi-server",
        }
        # Firma la transazione
        transaction["signature"] = self._sign_payload(
            transaction,
            secret=self.transaction_signing_secret,
        )
        return transaction

    # Verifica una transazione firmata ricevuta dal server.
    def verify_transaction(self, transaction: dict[str, Any]) -> bool:
        """Verifica la firma della transazione. Usato dal validatore prima di creare il blocco."""
        required_fields = {"event_type", "payload", "timestamp", "server_id", "signature"}
        if not required_fields.issubset(transaction.keys()):
            return False

        if transaction.get("server_id") != "fastapi-server":
            return False

        # Ricostruisci la transazione senza firma per verificare
        tx_data = {
            "event_type": transaction["event_type"],
            "payload": transaction["payload"],
            "timestamp": transaction["timestamp"],
            "server_id": transaction["server_id"],
        }
        expected_signature = self._sign_payload(
            tx_data,
            secret=self.transaction_signing_secret,
        )
        return hmac.compare_digest(transaction.get("signature", ""), expected_signature)

    # Restituisce l'hash del blocco precedente o "0" se la catena e' vuota.
    def _get_previous_hash(self) -> str:
        return self.chain["chain"][-1]["hash"] if self.chain.get("chain") else "0"

    # Crea un blocco nella blockchain di audit con il tipo di evento e il payload forniti.
    def create_block(
        self,
        event_type: str,
        payload: dict[str, Any],
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        previous_hash = self._get_previous_hash()
        return self._build_block(
            index=len(self.chain["chain"]),
            event_type=event_type,
            payload=payload,
            timestamp=timestamp,
            previous_hash=previous_hash,
        )

    # Valida una transazione della blockchain di audit controllando formato, hash e firma.
    def validate_block(self, transaction: dict[str, Any]) -> bool:
        required_fields = {"index", "timestamp", "event_type", "payload", "validator", "previous_hash", "hash", "signature"}
        if not required_fields.issubset(transaction.keys()):
            return False

        if transaction.get("validator") != "fastapi-poa-node":
            return False

        # Step 1: Ricostruisci il blocco senza firma per calcolare l'hash
        hash_payload = {
            "index": transaction["index"],
            "timestamp": transaction["timestamp"],
            "event_type": transaction["event_type"],
            "payload": transaction["payload"],
            "validator": transaction["validator"],
            "previous_hash": transaction["previous_hash"],
        }

        # Step 2: Verifica che l'hash del blocco sia corretto
        expected_hash = self._hash_payload(hash_payload)
        if transaction.get("hash") != expected_hash:
            return False

        # Step 3: Verifica la firma (HMAC-SHA256 dell'hash)
        expected_signature = self._sign_payload(
            {"hash": transaction["hash"], "validator": transaction["validator"]},
            secret=self.block_signing_secret,
        )
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
        
        # Funzione interna per analizzare una stringa di data/ora in un oggetto datetime con fuso orario UTC.
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
        
        # Analizza le stringhe di data/ora di inizio e fine in oggetti datetime.
        start_dt = _parse_time(start_time)
        end_dt = _parse_time(end_time)
        # Inizializza una lista per memorizzare i blocchi filtrati in base ai criteri forniti.
        filtered_blocks: list[dict[str, Any]] = []

        for block in self.chain.get("chain", []):
            payload = block.get("payload") or {}
            block_user = payload.get("user")
            block_event_type = block.get("event_type")
            block_timestamp = block.get("timestamp")
            block_dt = _parse_time(block_timestamp)

            if user and block_user != user:
                continue
            if event_type and event_type not in block_event_type:
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
            logger.warning("[AUDIT] validate_chain: chain vuota")
            return False

        expected_previous_hash = "0" # hash del blocco genesi

        # Validiamo ogni blocco della catena, controllando la firma, l'indice e l'hash del blocco precedente.
        for index, block in enumerate(chain):
            if not self.validate_block(block):
                logger.warning(
                    "[AUDIT] validate_chain: transazione non valida al blocco index=%s",
                    block.get("index"),
                )
                return False
            if block.get("index") != index:
                logger.warning(
                    "[AUDIT] validate_chain: indice incoerente al blocco atteso=%d trovato=%s",
                    index,
                    block.get("index"),
                )
                return False
            if index > 0 and block.get("previous_hash") != expected_previous_hash:
                logger.warning(
                    "[AUDIT] validate_chain: previous_hash incoerente al blocco index=%d",
                    index,
                )
                return False
            expected_previous_hash = block.get("hash", "")

        logger.info("[AUDIT] validate_chain: catena valida con %d blocchi", len(chain))
        return True

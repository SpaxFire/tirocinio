import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch # import patch per simulare comportamenti di oggetti durante i test
                                           # AsyncMock per simulare metodi asincroni durante i test

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from starlette.requests import Request

import app.main as main
from app.services.pending_queue import PendingAuditQueue
from app.services.audit_blockchain import AuditBlockchain, AuditTransactionSigner


# ---------------------------------------------------------------------------
# PendingAuditQueue unit tests
# ---------------------------------------------------------------------------

def test_push_and_pop_all(tmp_path):
    queue = PendingAuditQueue(queue_path=tmp_path / "pending.json")

    queue.push("get_request", {"path": "/posts"})
    queue.push("post_request", {"path": "/posts"})

    events = queue.pop_all()
    assert len(events) == 2
    assert events[0]["event_type"] == "get_request"
    assert events[1]["event_type"] == "post_request"


def test_pop_all_svuota_la_coda(tmp_path):
    queue = PendingAuditQueue(queue_path=tmp_path / "pending.json")

    queue.push("get_request", {"path": "/posts"})
    queue.pop_all()

    assert queue.is_empty() is True


def test_pop_all_su_coda_vuota_ritorna_lista_vuota(tmp_path):
    queue = PendingAuditQueue(queue_path=tmp_path / "pending.json")

    assert queue.pop_all() == []


def test_is_empty_inizialmente_vero(tmp_path):
    queue = PendingAuditQueue(queue_path=tmp_path / "pending.json")
    assert queue.is_empty() is True


def test_is_empty_falso_dopo_push(tmp_path):
    queue = PendingAuditQueue(queue_path=tmp_path / "pending.json")
    queue.push("get_request", {"path": "/posts"})
    assert queue.is_empty() is False


def test_coda_persistente_su_file(tmp_path):
    """La coda sopravvive alla ricreazione dell'istanza."""
    path = tmp_path / "pending.json"
    q1 = PendingAuditQueue(queue_path=path)
    q1.push("get_request", {"path": "/posts"})

    q2 = PendingAuditQueue(queue_path=path)
    events = q2.pop_all()
    assert len(events) == 1


# ---------------------------------------------------------------------------
# Middleware: salva in coda quando il validator è offline
# ---------------------------------------------------------------------------

def test_middleware_salva_in_coda_quando_validator_offline(tmp_path, monkeypatch):
    pending = PendingAuditQueue(queue_path=tmp_path / "pending.json")
    monkeypatch.setattr(main, "pending_queue", pending)

    # audit_client.enabled = True ma append_transaction fallisce (validator offline)
    mock_client = AsyncMock()
    mock_client.enabled = True
    mock_client.append_transaction = AsyncMock(return_value=False)
    monkeypatch.setattr(main, "audit_client", mock_client)

    test_app = FastAPI()
    test_app.add_middleware(main.CurrentUserMiddleware)

    @test_app.get("/items")
    async def read_items(request: Request):
        return PlainTextResponse("ok")

    client = TestClient(test_app)
    response = client.get("/items")

    assert response.status_code == 200
    assert pending.is_empty() is False
    # L'evento deve finire nella coda persistente
    queued = pending.pop_all()
    assert len(queued) == 1
    assert queued[0]["event_type"] == "get_request"


def test_middleware_sends_signed_blocks_to_validator(tmp_path, monkeypatch):
    """Test che il middleware invia transazioni firmate al validatore."""
    signer = AuditTransactionSigner(transaction_signing_secret="test-secret")
    verifier = AuditBlockchain(
        chain_path=tmp_path / "audit_chain.json",
        transaction_signing_secret="test-secret",
        block_signing_secret="unused-for-this-test",
    )
    monkeypatch.setattr(main, "audit_signer", signer)

    # Simula un client di audit che riceve le transazioni firmate
    mock_client = AsyncMock()
    mock_client.enabled = True
    received_transactions = []

    async def mock_append_transaction(transaction):
        received_transactions.append(transaction)
        return True

    mock_client.append_transaction = mock_append_transaction
    monkeypatch.setattr(main, "audit_client", mock_client)

    app = FastAPI()
    app.add_middleware(main.CurrentUserMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request):
        return PlainTextResponse("ok")

    client = TestClient(app)
    response = client.get("/test")

    assert response.status_code == 200
    # Verifica che sia stata ricevuta una transazione
    assert len(received_transactions) == 1
    transaction = received_transactions[0]
    # Verifica che la transazione abbia tutti i campi richiesti
    assert "event_type" in transaction
    assert "payload" in transaction
    assert "timestamp" in transaction
    assert "server_id" in transaction
    assert "signature" in transaction
    # Verifica che la transazione sia valida secondo il server
    assert verifier.verify_transaction(transaction) is True


def test_middleware_non_salva_in_coda_quando_validator_online(tmp_path, monkeypatch):
    pending = PendingAuditQueue(queue_path=tmp_path / "pending.json")
    monkeypatch.setattr(main, "pending_queue", pending)

    mock_client = AsyncMock()
    mock_client.enabled = True
    mock_client.append_transaction = AsyncMock(return_value=True)  # invio riuscito
    monkeypatch.setattr(main, "audit_client", mock_client)

    test_app = FastAPI()
    test_app.add_middleware(main.CurrentUserMiddleware)

    @test_app.get("/items")
    async def read_items(request: Request):
        return PlainTextResponse("ok")

    client = TestClient(test_app)
    client.get("/items")

    assert pending.is_empty() is True


# ---------------------------------------------------------------------------
# Flush task: invia gli eventi pendenti quando il validator torna online
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flush_invia_eventi_pendenti(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "audit_signer", AuditTransactionSigner(signing_secret="test-secret"))

    pending = PendingAuditQueue(queue_path=tmp_path / "pending.json")
    pending.push("get_request", {"path": "/posts"})
    pending.push("post_request", {"path": "/posts"})
    monkeypatch.setattr(main, "pending_queue", pending)

    mock_client = AsyncMock()
    mock_client.enabled = True # validator online
    mock_client.append_transaction = AsyncMock(return_value=True)
    monkeypatch.setattr(main, "audit_client", mock_client)

    # Eseguiamo un singolo ciclo del flush senza il loop infinito
    await main._flush_pending_events_once()

    assert mock_client.append_transaction.call_count == 2
    assert pending.is_empty() is True


@pytest.mark.asyncio
async def test_flush_rimette_in_coda_gli_eventi_falliti(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "audit_signer", AuditTransactionSigner(signing_secret="test-secret"))

    pending = PendingAuditQueue(queue_path=tmp_path / "pending.json")
    pending.push("get_request", {"path": "/posts"})
    monkeypatch.setattr(main, "pending_queue", pending)

    mock_client = AsyncMock()
    mock_client.enabled = True # validator online
    mock_client.append_transaction = AsyncMock(return_value=False)  # ancora offline
    monkeypatch.setattr(main, "audit_client", mock_client)

    await main._flush_pending_events_once()

    # L'evento deve essere tornato in coda
    assert pending.is_empty() is False
    assert len(pending.pop_all()) == 1


@pytest.mark.asyncio
async def test_flush_non_fa_nulla_se_coda_vuota(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "audit_signer", AuditTransactionSigner(signing_secret="test-secret"))

    pending = PendingAuditQueue(queue_path=tmp_path / "pending.json")
    monkeypatch.setattr(main, "pending_queue", pending)

    mock_client = AsyncMock()
    mock_client.enabled = True
    mock_client.append_transaction = AsyncMock(return_value=True)
    monkeypatch.setattr(main, "audit_client", mock_client)

    await main._flush_pending_events_once()

    mock_client.append_transaction.assert_not_called()

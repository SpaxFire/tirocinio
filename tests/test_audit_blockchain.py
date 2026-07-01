import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient # testclient per simulare richieste HTTP all'app FastAPI
from starlette.requests import Request

import app.main as main
from app.api.routes import pages as pages_route
from app.services.audit_blockchain import AuditBlockchain

# Test per verificare firma e validità della catena di audit
def test_transaction_is_signed_and_chain_is_valid(tmp_path):
    # Crea un percorso temporaneo per la catena di audit e un'istanza di AuditBlockchain temporanea per il test
    chain_path = tmp_path / "audit_chain.json"
    blockchain = AuditBlockchain(chain_path=chain_path, signing_secret="test-secret")
    
    # Crea blocco
    tx = blockchain.create_block(
        "request",
        {
            "method": "GET",
            "path": "/posts",
            "status_code": 200,
        },
    )

    assert blockchain.validate_transaction(tx) is True
    
    # Aggiunge un evento alla catena di audit
    blockchain.append_event(
        "request",
        {
            "method": "GET",
            "path": "/posts",
            "status_code": 200,
        },
    )

    stored = json.loads(chain_path.read_text())
    assert len(stored["chain"]) >= 2
    assert blockchain.validate_chain() is True

# Test per verificare che una transazione con firma non valida venga rifiutata
def test_invalid_signature_is_rejected(tmp_path):
    chain_path = tmp_path / "audit_chain.json"
    blockchain = AuditBlockchain(chain_path=chain_path, signing_secret="test-secret")

    tx = blockchain.create_block("request", {"path": "/posts"})
    tx["signature"] = "tampered"

    assert blockchain.validate_transaction(tx) is False

# Test Middleware intercetta la richiesta HTTP, identifica l’utente e registra l’evento nella audit chain.
def test_middleware_logs_http_method_based_event_type(tmp_path, monkeypatch):
    # instanzia un AuditBlockchain temporaneo per il test
    chain_path = tmp_path / "audit_chain.json"
    blockchain = AuditBlockchain(chain_path=chain_path, signing_secret="test-secret")
    monkeypatch.setattr(main, "audit_blockchain", blockchain) # sostituisce l'istanza di AuditBlockchain nel modulo main con quella creata per il test

    app = FastAPI()
    app.add_middleware(main.CurrentUserMiddleware) # aggiunge il middleware CurrentUserMiddleware all'app FastAPI per intercettare le richieste

    # Definisce un endpoint di test che restituisce "ok" per verificare che la richiesta HTTP venga intercettata e registrata.

    @app.get("/items") 
    async def read_items(request: Request):
        return PlainTextResponse("ok")

    client = TestClient(app) # crea un client di test per simulare richieste HTTP all'app FastAPI
    response = client.get("/items") # get

    assert response.status_code == 200
    stored = json.loads(chain_path.read_text())
    assert stored["chain"][-1]["event_type"] == "get_request"


# Test filtro temporale e per utente nella catena di audit
def test_filter_audit_chain_by_user_event_and_time(tmp_path):
    chain_path = tmp_path / "audit_chain.json"
    blockchain = AuditBlockchain(chain_path=chain_path, signing_secret="test-secret")

    now = datetime.now(timezone.utc)
    blockchain.chain["chain"][0]["timestamp"] = (now - timedelta(hours=3)).isoformat()
    blockchain.append_event("get_request", {"path": "/posts", "user": "alice"})
    blockchain.append_event("post_request", {"path": "/posts", "user": "bob"})
    blockchain.chain["chain"][-1]["timestamp"] = (now - timedelta(hours=1)).isoformat()

    filtered = blockchain.filter_chain(
        user="alice",
        event_type="get_request",
        start_time=(now - timedelta(hours=2)).isoformat(),
        end_time=(now + timedelta(minutes=5)).isoformat(),
    )

    assert len(filtered) == 1
    assert filtered[0]["payload"]["user"] == "alice"
    assert filtered[0]["event_type"] == "get_request"


# Test per verificare che la pagina di audit dell'amministratore sia vietata per utenti non amministratori
def test_admin_audit_page_is_forbidden_for_non_admin(tmp_path):
    chain_path = tmp_path / "audit_chain.json"
    blockchain = AuditBlockchain(chain_path=chain_path, signing_secret="test-secret")
    blockchain.append_event("request", {"path": "/posts"})
    pages_route.audit_blockchain = blockchain

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/admin/audit",
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 123),
            "server": ("testserver", 80),
            "scheme": "http",
            "http_version": "1.1",
        }
    )
    # Verifica che venga sollevata un'eccezione HTTPException quando un utente non amministratore tenta accesso.
    with pytest.raises(HTTPException) as exc: 
        asyncio.run(
            pages_route.admin_audit_page(
                request=request,
                current_user=SimpleNamespace(username="alice", role="USER"),
            )
        )

    assert exc.value.status_code == 403


# Test per verificare che la pagina di audit dell'amministratore restituisca contenuti parziali per richieste HTMX
def test_admin_audit_page_returns_partial_content_for_htmx(tmp_path):
    chain_path = tmp_path / "audit_chain.json"
    blockchain = AuditBlockchain(chain_path=chain_path, signing_secret="test-secret")
    blockchain.append_event("request", {"path": "/posts"})
    pages_route.audit_blockchain = blockchain

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/admin/audit",
            "headers": [(b"hx-request", b"true")],
            "query_string": b"",
            "client": ("testclient", 123),
            "server": ("testserver", 80),
            "scheme": "http",
            "http_version": "1.1",
        }
    )
    # Verifica che la risposta contenga solo il contenuto parziale della pagina di audit per richieste HTMX.
    response = asyncio.run(
        pages_route.admin_audit_page(
            request=request,
            current_user=SimpleNamespace(username="admin", role="ADMIN"),
        )
    )

    body = response.body.decode("utf-8")
    assert "Audit blockchain" in body # Verifica che la risposta contenga il titolo della pagina di audit
    assert "Stai seguendo" not in body # Verifica che la risposta non contenga il contenuto completo della pagina di audit
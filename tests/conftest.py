import pytest

import app.main as main
from app.services.pending_queue import PendingAuditQueue


@pytest.fixture(autouse=True)
def isolate_audit_files(tmp_path, monkeypatch):
    """Keep tests from reading/writing repository audit files."""
    pending_path = tmp_path / "pending_audit_events.json"
    chain_path = tmp_path / "audit_chain.json"

    pending_path.write_text("[]\n", encoding="utf-8")

    monkeypatch.setenv("AUDIT_PENDING_PATH", str(pending_path))
    monkeypatch.setenv("AUDIT_CHAIN_PATH", str(chain_path))
    monkeypatch.setattr(main, "pending_queue", PendingAuditQueue(queue_path=pending_path))

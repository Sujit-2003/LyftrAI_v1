"""
Test fixtures and configuration.
"""
import hashlib
import hmac
import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Set test environment variables before importing app
os.environ["WEBHOOK_SECRET"] = "testsecret"
os.environ["LOG_LEVEL"] = "DEBUG"


@pytest.fixture(scope="function")
def test_db_path():
    """Create a temporary database file for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture(scope="function")
def client(test_db_path):
    """Create a test client with isolated database."""
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

    # Import after setting environment
    from app.main import app
    from app.storage import init_database, _db
    import app.storage as storage_module

    # Reset the global database instance
    storage_module._db = None

    # Initialize fresh database
    init_database()

    with TestClient(app) as c:
        yield c

    # Cleanup
    storage_module._db = None


@pytest.fixture
def webhook_secret():
    """Return the test webhook secret."""
    return "testsecret"


def compute_signature(secret: str, body: bytes) -> str:
    """Compute HMAC-SHA256 signature for request body."""
    return hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()


@pytest.fixture
def make_signature(webhook_secret):
    """Factory fixture to create valid signatures."""
    def _make_signature(body: dict) -> str:
        body_bytes = json.dumps(body).encode("utf-8")
        return compute_signature(webhook_secret, body_bytes)
    return _make_signature


@pytest.fixture
def valid_message():
    """Return a valid webhook message payload."""
    return {
        "message_id": "m1",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Hello",
    }


@pytest.fixture
def send_webhook(client, webhook_secret):
    """Factory fixture to send webhook requests with valid signature."""
    def _send(body: dict, signature: str = None):
        body_bytes = json.dumps(body).encode("utf-8")
        if signature is None:
            signature = compute_signature(webhook_secret, body_bytes)
        return client.post(
            "/webhook",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature,
            },
        )
    return _send

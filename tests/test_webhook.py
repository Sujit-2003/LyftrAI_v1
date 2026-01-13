"""
Tests for POST /webhook endpoint.
"""
import json

import pytest


class TestWebhookSignature:
    """Tests for HMAC signature validation."""

    def test_missing_signature_returns_401(self, client, valid_message):
        """Test that missing X-Signature header returns 401."""
        response = client.post(
            "/webhook",
            json=valid_message,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 401
        assert response.json() == {"detail": "invalid signature"}

    def test_invalid_signature_returns_401(self, client, valid_message):
        """Test that invalid signature returns 401."""
        response = client.post(
            "/webhook",
            json=valid_message,
            headers={
                "Content-Type": "application/json",
                "X-Signature": "invalid123",
            },
        )
        assert response.status_code == 401
        assert response.json() == {"detail": "invalid signature"}

    def test_valid_signature_returns_200(self, send_webhook, valid_message):
        """Test that valid signature returns 200."""
        response = send_webhook(valid_message)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestWebhookValidation:
    """Tests for payload validation."""

    def test_empty_message_id_returns_422(self, send_webhook):
        """Test that empty message_id returns 422."""
        payload = {
            "message_id": "",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello",
        }
        response = send_webhook(payload)
        assert response.status_code == 422

    def test_invalid_from_format_returns_422(self, send_webhook):
        """Test that invalid 'from' format returns 422."""
        payload = {
            "message_id": "m1",
            "from": "9876543210",  # Missing +
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello",
        }
        response = send_webhook(payload)
        assert response.status_code == 422

    def test_invalid_to_format_returns_422(self, send_webhook):
        """Test that invalid 'to' format returns 422."""
        payload = {
            "message_id": "m1",
            "from": "+919876543210",
            "to": "14155550100",  # Missing +
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello",
        }
        response = send_webhook(payload)
        assert response.status_code == 422

    def test_invalid_ts_format_returns_422(self, send_webhook):
        """Test that invalid timestamp format returns 422."""
        payload = {
            "message_id": "m1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00",  # Missing Z
            "text": "Hello",
        }
        response = send_webhook(payload)
        assert response.status_code == 422

    def test_text_exceeding_max_length_returns_422(self, send_webhook):
        """Test that text exceeding 4096 characters returns 422."""
        payload = {
            "message_id": "m1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "x" * 4097,
        }
        response = send_webhook(payload)
        assert response.status_code == 422

    def test_optional_text_can_be_null(self, send_webhook):
        """Test that text field is optional."""
        payload = {
            "message_id": "m1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
        }
        response = send_webhook(payload)
        assert response.status_code == 200

    def test_optional_text_can_be_empty(self, send_webhook):
        """Test that text field can be empty string."""
        payload = {
            "message_id": "m2",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "",
        }
        response = send_webhook(payload)
        assert response.status_code == 200


class TestWebhookIdempotency:
    """Tests for idempotent message insertion."""

    def test_first_insert_returns_200(self, send_webhook, valid_message):
        """Test that first insert returns 200."""
        response = send_webhook(valid_message)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_duplicate_insert_returns_200(self, send_webhook, valid_message):
        """Test that duplicate insert also returns 200 (idempotent)."""
        # First insert
        response1 = send_webhook(valid_message)
        assert response1.status_code == 200

        # Duplicate insert
        response2 = send_webhook(valid_message)
        assert response2.status_code == 200
        assert response2.json() == {"status": "ok"}

    def test_duplicate_does_not_create_second_row(self, send_webhook, client, valid_message):
        """Test that duplicate insert doesn't create a second row."""
        # First insert
        send_webhook(valid_message)

        # Duplicate insert
        send_webhook(valid_message)

        # Check only one message exists
        response = client.get("/messages")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["data"]) == 1

    def test_different_message_ids_create_separate_rows(self, send_webhook, client):
        """Test that different message_ids create separate rows."""
        msg1 = {
            "message_id": "m1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello 1",
        }
        msg2 = {
            "message_id": "m2",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:01:00Z",
            "text": "Hello 2",
        }

        send_webhook(msg1)
        send_webhook(msg2)

        response = client.get("/messages")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["data"]) == 2

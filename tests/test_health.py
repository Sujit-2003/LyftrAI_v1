"""
Tests for health probe endpoints.
"""
import os

import pytest


class TestLiveness:
    """Tests for GET /health/live endpoint."""

    def test_liveness_returns_200(self, client):
        """Test that liveness probe always returns 200."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestReadiness:
    """Tests for GET /health/ready endpoint."""

    def test_readiness_returns_200_when_configured(self, client):
        """Test that readiness returns 200 when properly configured."""
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestMetrics:
    """Tests for GET /metrics endpoint."""

    def test_metrics_returns_200(self, client):
        """Test that metrics endpoint returns 200."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")

    def test_metrics_contains_http_requests_total(self, client):
        """Test that metrics contains http_requests_total."""
        # Make some requests first
        client.get("/health/live")
        client.get("/messages")

        response = client.get("/metrics")
        content = response.text

        assert "http_requests_total" in content

    def test_metrics_contains_webhook_requests_total(self, send_webhook, client):
        """Test that metrics contains webhook_requests_total."""
        # Make a webhook request
        msg = {
            "message_id": "m1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
        }
        send_webhook(msg)

        response = client.get("/metrics")
        content = response.text

        assert "webhook_requests_total" in content

    def test_metrics_contains_latency_histogram(self, client):
        """Test that metrics contains request latency histogram."""
        # Make some requests
        client.get("/health/live")

        response = client.get("/metrics")
        content = response.text

        assert "request_latency_ms" in content

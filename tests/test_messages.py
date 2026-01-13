"""
Tests for GET /messages endpoint.
"""
import pytest


class TestMessagesPagination:
    """Tests for pagination functionality."""

    @pytest.fixture(autouse=True)
    def seed_messages(self, send_webhook):
        """Seed database with test messages."""
        messages = [
            {"message_id": f"m{i}", "from": "+919876543210", "to": "+14155550100",
             "ts": f"2025-01-15T10:0{i}:00Z", "text": f"Message {i}"}
            for i in range(5)
        ]
        for msg in messages:
            send_webhook(msg)

    def test_default_pagination(self, client):
        """Test default pagination values."""
        response = client.get("/messages")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 50
        assert data["offset"] == 0
        assert data["total"] == 5
        assert len(data["data"]) == 5

    def test_custom_limit(self, client):
        """Test custom limit parameter."""
        response = client.get("/messages?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 2
        assert data["total"] == 5
        assert len(data["data"]) == 2

    def test_custom_offset(self, client):
        """Test custom offset parameter."""
        response = client.get("/messages?offset=2")
        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 2
        assert data["total"] == 5
        assert len(data["data"]) == 3

    def test_limit_and_offset(self, client):
        """Test combination of limit and offset."""
        response = client.get("/messages?limit=2&offset=1")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 2
        assert data["offset"] == 1
        assert data["total"] == 5
        assert len(data["data"]) == 2
        # Should skip first message
        assert data["data"][0]["message_id"] == "m1"

    def test_limit_max_100(self, client):
        """Test that limit cannot exceed 100."""
        response = client.get("/messages?limit=101")
        assert response.status_code == 422

    def test_limit_min_1(self, client):
        """Test that limit cannot be less than 1."""
        response = client.get("/messages?limit=0")
        assert response.status_code == 422

    def test_offset_min_0(self, client):
        """Test that offset cannot be negative."""
        response = client.get("/messages?offset=-1")
        assert response.status_code == 422


class TestMessagesOrdering:
    """Tests for message ordering."""

    def test_ordered_by_ts_asc(self, send_webhook, client):
        """Test that messages are ordered by timestamp ascending."""
        messages = [
            {"message_id": "m3", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T12:00:00Z", "text": "Third"},
            {"message_id": "m1", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T10:00:00Z", "text": "First"},
            {"message_id": "m2", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T11:00:00Z", "text": "Second"},
        ]
        for msg in messages:
            send_webhook(msg)

        response = client.get("/messages")
        data = response.json()

        assert data["data"][0]["message_id"] == "m1"
        assert data["data"][1]["message_id"] == "m2"
        assert data["data"][2]["message_id"] == "m3"

    def test_ordered_by_message_id_for_same_ts(self, send_webhook, client):
        """Test that messages with same timestamp are ordered by message_id."""
        messages = [
            {"message_id": "m3", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T10:00:00Z", "text": "Third"},
            {"message_id": "m1", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T10:00:00Z", "text": "First"},
            {"message_id": "m2", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T10:00:00Z", "text": "Second"},
        ]
        for msg in messages:
            send_webhook(msg)

        response = client.get("/messages")
        data = response.json()

        assert data["data"][0]["message_id"] == "m1"
        assert data["data"][1]["message_id"] == "m2"
        assert data["data"][2]["message_id"] == "m3"


class TestMessagesFilters:
    """Tests for message filtering."""

    @pytest.fixture(autouse=True)
    def seed_messages(self, send_webhook):
        """Seed database with test messages for filtering."""
        messages = [
            {"message_id": "m1", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T09:00:00Z", "text": "Hello World"},
            {"message_id": "m2", "from": "+911234567890", "to": "+14155550100",
             "ts": "2025-01-15T10:00:00Z", "text": "Hi there"},
            {"message_id": "m3", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T11:00:00Z", "text": "Goodbye World"},
            {"message_id": "m4", "from": "+911234567890", "to": "+14155550100",
             "ts": "2025-01-15T12:00:00Z", "text": "See you"},
        ]
        for msg in messages:
            send_webhook(msg)

    def test_filter_by_from(self, client):
        """Test filtering by sender phone number."""
        response = client.get("/messages?from=%2B919876543210")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for msg in data["data"]:
            assert msg["from"] == "+919876543210"

    def test_filter_by_since(self, client):
        """Test filtering by timestamp (since)."""
        response = client.get("/messages?since=2025-01-15T10:30:00Z")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        # Should only have m3 and m4
        message_ids = [m["message_id"] for m in data["data"]]
        assert "m3" in message_ids
        assert "m4" in message_ids

    def test_filter_by_q_text_search(self, client):
        """Test free-text search in message text."""
        response = client.get("/messages?q=World")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        message_ids = [m["message_id"] for m in data["data"]]
        assert "m1" in message_ids
        assert "m3" in message_ids

    def test_filter_by_q_case_insensitive(self, client):
        """Test that text search is case-insensitive."""
        response = client.get("/messages?q=world")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    def test_combined_filters(self, client):
        """Test combining multiple filters."""
        response = client.get("/messages?from=%2B919876543210&q=World")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for msg in data["data"]:
            assert msg["from"] == "+919876543210"
            assert "World" in msg["text"]

    def test_filter_with_pagination(self, client):
        """Test filters work correctly with pagination."""
        response = client.get("/messages?from=%2B919876543210&limit=1")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # Total matching filter
        assert len(data["data"]) == 1  # Limited by pagination
        assert data["limit"] == 1


class TestMessagesResponseShape:
    """Tests for response shape and structure."""

    def test_empty_database_returns_empty_data(self, client):
        """Test that empty database returns empty data array."""
        response = client.get("/messages")
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["total"] == 0

    def test_response_contains_all_fields(self, send_webhook, client):
        """Test that response contains all required fields."""
        msg = {
            "message_id": "m1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello",
        }
        send_webhook(msg)

        response = client.get("/messages")
        data = response.json()

        assert "data" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

        msg_data = data["data"][0]
        assert "message_id" in msg_data
        assert "from" in msg_data
        assert "to" in msg_data
        assert "ts" in msg_data
        assert "text" in msg_data

    def test_null_text_in_response(self, send_webhook, client):
        """Test that null text is properly returned."""
        msg = {
            "message_id": "m1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
        }
        send_webhook(msg)

        response = client.get("/messages")
        data = response.json()
        assert data["data"][0]["text"] is None

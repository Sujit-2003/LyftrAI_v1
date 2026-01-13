"""
Tests for GET /stats endpoint.
"""
import pytest


class TestStatsEmpty:
    """Tests for stats with empty database."""

    def test_empty_database_stats(self, client):
        """Test stats response with no messages."""
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_messages"] == 0
        assert data["senders_count"] == 0
        assert data["messages_per_sender"] == []
        assert data["first_message_ts"] is None
        assert data["last_message_ts"] is None


class TestStatsTotalMessages:
    """Tests for total message count."""

    def test_total_messages_count(self, send_webhook, client):
        """Test that total_messages counts all messages."""
        for i in range(5):
            msg = {
                "message_id": f"m{i}",
                "from": "+919876543210",
                "to": "+14155550100",
                "ts": f"2025-01-15T10:0{i}:00Z",
                "text": f"Message {i}",
            }
            send_webhook(msg)

        response = client.get("/stats")
        data = response.json()
        assert data["total_messages"] == 5


class TestStatsSendersCount:
    """Tests for unique senders count."""

    def test_senders_count(self, send_webhook, client):
        """Test that senders_count counts unique senders."""
        messages = [
            {"message_id": "m1", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T10:00:00Z"},
            {"message_id": "m2", "from": "+911234567890", "to": "+14155550100",
             "ts": "2025-01-15T10:01:00Z"},
            {"message_id": "m3", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T10:02:00Z"},
            {"message_id": "m4", "from": "+915555555555", "to": "+14155550100",
             "ts": "2025-01-15T10:03:00Z"},
        ]
        for msg in messages:
            send_webhook(msg)

        response = client.get("/stats")
        data = response.json()
        assert data["senders_count"] == 3


class TestStatsMessagesPerSender:
    """Tests for messages_per_sender aggregation."""

    def test_messages_per_sender_count(self, send_webhook, client):
        """Test that messages_per_sender shows correct counts."""
        messages = [
            {"message_id": "m1", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T10:00:00Z"},
            {"message_id": "m2", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T10:01:00Z"},
            {"message_id": "m3", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T10:02:00Z"},
            {"message_id": "m4", "from": "+911234567890", "to": "+14155550100",
             "ts": "2025-01-15T10:03:00Z"},
            {"message_id": "m5", "from": "+911234567890", "to": "+14155550100",
             "ts": "2025-01-15T10:04:00Z"},
        ]
        for msg in messages:
            send_webhook(msg)

        response = client.get("/stats")
        data = response.json()

        # Should have 2 senders
        assert len(data["messages_per_sender"]) == 2

        # First sender should have 3 messages (sorted by count desc)
        assert data["messages_per_sender"][0]["from"] == "+919876543210"
        assert data["messages_per_sender"][0]["count"] == 3

        # Second sender should have 2 messages
        assert data["messages_per_sender"][1]["from"] == "+911234567890"
        assert data["messages_per_sender"][1]["count"] == 2

    def test_messages_per_sender_sorted_desc(self, send_webhook, client):
        """Test that messages_per_sender is sorted by count descending."""
        messages = [
            {"message_id": "m1", "from": "+911111111111", "to": "+14155550100",
             "ts": "2025-01-15T10:00:00Z"},
            {"message_id": "m2", "from": "+912222222222", "to": "+14155550100",
             "ts": "2025-01-15T10:01:00Z"},
            {"message_id": "m3", "from": "+912222222222", "to": "+14155550100",
             "ts": "2025-01-15T10:02:00Z"},
            {"message_id": "m4", "from": "+913333333333", "to": "+14155550100",
             "ts": "2025-01-15T10:03:00Z"},
            {"message_id": "m5", "from": "+913333333333", "to": "+14155550100",
             "ts": "2025-01-15T10:04:00Z"},
            {"message_id": "m6", "from": "+913333333333", "to": "+14155550100",
             "ts": "2025-01-15T10:05:00Z"},
        ]
        for msg in messages:
            send_webhook(msg)

        response = client.get("/stats")
        data = response.json()

        # Should be sorted by count descending
        counts = [s["count"] for s in data["messages_per_sender"]]
        assert counts == sorted(counts, reverse=True)

    def test_messages_per_sender_max_10(self, send_webhook, client):
        """Test that messages_per_sender returns at most 10 entries."""
        # Create 12 unique senders
        for i in range(12):
            phone = f"+9100000000{i:02d}"
            msg = {
                "message_id": f"m{i}",
                "from": phone,
                "to": "+14155550100",
                "ts": f"2025-01-15T10:{i:02d}:00Z",
            }
            send_webhook(msg)

        response = client.get("/stats")
        data = response.json()

        assert data["senders_count"] == 12
        assert len(data["messages_per_sender"]) <= 10


class TestStatsTimestamps:
    """Tests for first and last message timestamps."""

    def test_first_and_last_message_ts(self, send_webhook, client):
        """Test that first and last timestamps are correct."""
        messages = [
            {"message_id": "m2", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T11:00:00Z"},
            {"message_id": "m1", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T09:00:00Z"},  # Earliest
            {"message_id": "m3", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T15:00:00Z"},  # Latest
            {"message_id": "m4", "from": "+919876543210", "to": "+14155550100",
             "ts": "2025-01-15T12:00:00Z"},
        ]
        for msg in messages:
            send_webhook(msg)

        response = client.get("/stats")
        data = response.json()

        assert data["first_message_ts"] == "2025-01-15T09:00:00Z"
        assert data["last_message_ts"] == "2025-01-15T15:00:00Z"

    def test_single_message_timestamps(self, send_webhook, client):
        """Test timestamps with single message."""
        msg = {
            "message_id": "m1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
        }
        send_webhook(msg)

        response = client.get("/stats")
        data = response.json()

        assert data["first_message_ts"] == "2025-01-15T10:00:00Z"
        assert data["last_message_ts"] == "2025-01-15T10:00:00Z"


class TestStatsResponseShape:
    """Tests for stats response structure."""

    def test_response_contains_all_fields(self, client):
        """Test that response contains all required fields."""
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()

        assert "total_messages" in data
        assert "senders_count" in data
        assert "messages_per_sender" in data
        assert "first_message_ts" in data
        assert "last_message_ts" in data

    def test_messages_per_sender_entry_shape(self, send_webhook, client):
        """Test that messages_per_sender entries have correct shape."""
        msg = {
            "message_id": "m1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
        }
        send_webhook(msg)

        response = client.get("/stats")
        data = response.json()

        entry = data["messages_per_sender"][0]
        assert "from" in entry
        assert "count" in entry
        assert isinstance(entry["count"], int)

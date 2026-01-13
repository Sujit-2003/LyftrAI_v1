"""
SQLite database operations and storage layer.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional, Tuple

from app.config import get_settings


class Database:
    """SQLite database handler."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_settings().db_path
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection as a context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Initialize the database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    from_msisdn TEXT NOT NULL,
                    to_msisdn TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    text TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            # Create indexes for common query patterns
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_ts
                ON messages(ts)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_from
                ON messages(from_msisdn)
            """)
            conn.commit()

    def is_ready(self) -> bool:
        """Check if database is ready and schema is applied."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
                )
                return cursor.fetchone() is not None
        except Exception:
            return False

    def insert_message(
        self,
        message_id: str,
        from_msisdn: str,
        to_msisdn: str,
        ts: str,
        text: Optional[str],
    ) -> Tuple[bool, bool]:
        """
        Insert a message into the database.

        Returns:
            Tuple of (success: bool, is_duplicate: bool)
        """
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO messages (message_id, from_msisdn, to_msisdn, ts, text, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (message_id, from_msisdn, to_msisdn, ts, text, created_at),
                )
                conn.commit()
                return True, False
            except sqlite3.IntegrityError:
                # Duplicate message_id - this is expected for idempotency
                return True, True

    def get_messages(
        self,
        limit: int = 50,
        offset: int = 0,
        from_filter: Optional[str] = None,
        since: Optional[str] = None,
        q: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get paginated messages with optional filters.

        Returns:
            Tuple of (messages list, total count matching filters)
        """
        conditions: List[str] = []
        params: List[Any] = []

        if from_filter:
            conditions.append("from_msisdn = ?")
            params.append(from_filter)

        if since:
            conditions.append("ts >= ?")
            params.append(since)

        if q:
            conditions.append("text LIKE ?")
            params.append(f"%{q}%")

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get total count
            count_query = f"SELECT COUNT(*) FROM messages{where_clause}"
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Get paginated results
            query = f"""
                SELECT message_id, from_msisdn, to_msisdn, ts, text
                FROM messages
                {where_clause}
                ORDER BY ts ASC, message_id ASC
                LIMIT ? OFFSET ?
            """
            cursor.execute(query, params + [limit, offset])
            rows = cursor.fetchall()

            messages = [
                {
                    "message_id": row["message_id"],
                    "from": row["from_msisdn"],
                    "to": row["to_msisdn"],
                    "ts": row["ts"],
                    "text": row["text"],
                }
                for row in rows
            ]

            return messages, total

    def get_stats(self) -> Dict[str, Any]:
        """Get message statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total messages
            cursor.execute("SELECT COUNT(*) FROM messages")
            total_messages = cursor.fetchone()[0]

            # Unique senders count
            cursor.execute("SELECT COUNT(DISTINCT from_msisdn) FROM messages")
            senders_count = cursor.fetchone()[0]

            # Top senders (up to 10)
            cursor.execute("""
                SELECT from_msisdn, COUNT(*) as count
                FROM messages
                GROUP BY from_msisdn
                ORDER BY count DESC
                LIMIT 10
            """)
            messages_per_sender = [
                {"from": row["from_msisdn"], "count": row["count"]}
                for row in cursor.fetchall()
            ]

            # First and last message timestamps
            cursor.execute("SELECT MIN(ts) as first_ts, MAX(ts) as last_ts FROM messages")
            row = cursor.fetchone()
            first_message_ts = row["first_ts"] if row else None
            last_message_ts = row["last_ts"] if row else None

            return {
                "total_messages": total_messages,
                "senders_count": senders_count,
                "messages_per_sender": messages_per_sender,
                "first_message_ts": first_message_ts,
                "last_message_ts": last_message_ts,
            }


# Global database instance
_db: Optional[Database] = None


def get_database() -> Database:
    """Get or create the global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db


def init_database() -> None:
    """Initialize the database schema."""
    db = get_database()
    db.init_schema()

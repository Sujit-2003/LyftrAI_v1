"""
Pydantic models for request/response validation.
"""
import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# E.164 format: starts with +, followed by digits only (max 15 digits typically)
E164_PATTERN = re.compile(r"^\+\d+$")


class WebhookMessage(BaseModel):
    """Incoming webhook message payload."""

    message_id: str = Field(..., min_length=1, description="Unique message identifier")
    from_: str = Field(..., alias="from", description="Sender phone number in E.164 format")
    to: str = Field(..., description="Recipient phone number in E.164 format")
    ts: str = Field(..., description="Timestamp in ISO-8601 UTC format with Z suffix")
    text: Optional[str] = Field(None, max_length=4096, description="Message text content")

    @field_validator("from_", mode="before")
    @classmethod
    def validate_from(cls, v: str) -> str:
        if not E164_PATTERN.match(v):
            raise ValueError("must be in E.164 format (starts with +, followed by digits)")
        return v

    @field_validator("to")
    @classmethod
    def validate_to(cls, v: str) -> str:
        if not E164_PATTERN.match(v):
            raise ValueError("must be in E.164 format (starts with +, followed by digits)")
        return v

    @field_validator("ts")
    @classmethod
    def validate_ts(cls, v: str) -> str:
        if not v.endswith("Z"):
            raise ValueError("must be ISO-8601 UTC timestamp with Z suffix")
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("must be valid ISO-8601 UTC timestamp")
        return v

    model_config = {"populate_by_name": True}


class WebhookResponse(BaseModel):
    """Webhook success response."""

    status: str = "ok"


class MessageItem(BaseModel):
    """Single message in list response."""

    message_id: str
    from_: str = Field(..., alias="from", serialization_alias="from")
    to: str
    ts: str
    text: Optional[str] = None

    model_config = {"populate_by_name": True}


class MessagesResponse(BaseModel):
    """Paginated messages list response."""

    data: List[MessageItem]
    total: int
    limit: int
    offset: int


class SenderCount(BaseModel):
    """Message count per sender."""

    from_: str = Field(..., alias="from", serialization_alias="from")
    count: int

    model_config = {"populate_by_name": True}


class StatsResponse(BaseModel):
    """Analytics statistics response."""

    total_messages: int
    senders_count: int
    messages_per_sender: List[SenderCount]
    first_message_ts: Optional[str] = None
    last_message_ts: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str

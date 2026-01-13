"""
FastAPI application with webhook ingestion, message listing, and observability endpoints.
"""
import hashlib
import hmac
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import get_settings
from app.logging_utils import RequestLogContext, get_logger, log_request, setup_logging
from app.metrics import get_metrics
from app.models import (
    ErrorResponse,
    HealthResponse,
    MessageItem,
    MessagesResponse,
    SenderCount,
    StatsResponse,
    WebhookMessage,
    WebhookResponse,
)
from app.storage import get_database, init_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    setup_logging()
    logger = get_logger()
    settings = get_settings()

    if not settings.webhook_secret:
        logger.error("WEBHOOK_SECRET environment variable is not set")
    else:
        logger.info("Application starting up")
        init_database()
        logger.info("Database initialized")

    yield

    # Shutdown
    logger.info("Application shutting down")


app = FastAPI(
    title="Lyftr Webhook API",
    description="Production-style FastAPI service for WhatsApp-like message ingestion",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Middleware for request logging and metrics collection."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.time()

    # Read body for webhook signature verification (cache it)
    if request.url.path == "/webhook" and request.method == "POST":
        body = await request.body()
        request.state.raw_body = body

    response = await call_next(request)

    # Calculate latency
    latency_ms = (time.time() - start_time) * 1000

    # Update metrics
    metrics = get_metrics()
    metrics.inc_http_request(request.url.path, response.status_code)
    metrics.observe_latency(latency_ms)

    # Log request (skip health probes for cleaner logs unless DEBUG)
    logger = get_logger()
    if not request.url.path.startswith("/health") or logger.level <= logging.DEBUG:
        ctx = RequestLogContext(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=round(latency_ms, 2),
        )

        # Add webhook-specific fields
        if hasattr(request.state, "webhook_message_id"):
            ctx.message_id = request.state.webhook_message_id
        if hasattr(request.state, "webhook_dup"):
            ctx.dup = request.state.webhook_dup
        if hasattr(request.state, "webhook_result"):
            ctx.result = request.state.webhook_result

        log_level = logging.INFO if response.status_code < 400 else logging.ERROR
        log_request(logger, ctx, level=log_level)

    return response


def verify_signature(secret: str, body: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post(
    "/webhook",
    response_model=WebhookResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid signature"},
        422: {"description": "Validation error"},
    },
)
async def webhook(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
):
    """
    Ingest inbound WhatsApp-like messages with HMAC signature validation.

    - Validates X-Signature header using HMAC-SHA256
    - Ensures idempotency via message_id uniqueness
    - Returns 200 for both new and duplicate messages
    """
    settings = get_settings()
    logger = get_logger()
    metrics = get_metrics()

    # Get raw body (cached by middleware)
    raw_body = getattr(request.state, "raw_body", await request.body())

    # Validate signature
    if not x_signature or not settings.webhook_secret:
        request.state.webhook_result = "invalid_signature"
        metrics.inc_webhook_request("invalid_signature")
        raise HTTPException(
            status_code=401,
            detail="invalid signature",
        )

    if not verify_signature(settings.webhook_secret, raw_body, x_signature):
        request.state.webhook_result = "invalid_signature"
        metrics.inc_webhook_request("invalid_signature")
        raise HTTPException(
            status_code=401,
            detail="invalid signature",
        )

    # Parse and validate payload
    try:
        import json

        payload = json.loads(raw_body)
        message = WebhookMessage(**payload)
    except Exception as e:
        request.state.webhook_result = "validation_error"
        metrics.inc_webhook_request("validation_error")
        raise HTTPException(
            status_code=422,
            detail=str(e),
        )

    # Store message_id for logging
    request.state.webhook_message_id = message.message_id

    # Insert into database
    db = get_database()
    success, is_duplicate = db.insert_message(
        message_id=message.message_id,
        from_msisdn=message.from_,
        to_msisdn=message.to,
        ts=message.ts,
        text=message.text,
    )

    request.state.webhook_dup = is_duplicate

    if is_duplicate:
        request.state.webhook_result = "duplicate"
        metrics.inc_webhook_request("duplicate")
    else:
        request.state.webhook_result = "created"
        metrics.inc_webhook_request("created")

    return WebhookResponse(status="ok")


@app.get("/messages", response_model=MessagesResponse)
async def list_messages(
    limit: int = Query(default=50, ge=1, le=100, description="Number of messages to return"),
    offset: int = Query(default=0, ge=0, description="Number of messages to skip"),
    from_: Optional[str] = Query(
        default=None,
        alias="from",
        description="Filter by sender phone number",
    ),
    since: Optional[str] = Query(
        default=None,
        description="Filter messages with ts >= this ISO-8601 timestamp",
    ),
    q: Optional[str] = Query(
        default=None,
        description="Free-text search in message text",
    ),
):
    """
    List stored messages with pagination and filters.

    - Supports filtering by sender (from), timestamp (since), and text search (q)
    - Results ordered by ts ASC, message_id ASC
    - Returns total count matching filters (ignoring pagination)
    """
    db = get_database()
    messages, total = db.get_messages(
        limit=limit,
        offset=offset,
        from_filter=from_,
        since=since,
        q=q,
    )

    return MessagesResponse(
        data=[
            MessageItem(
                message_id=m["message_id"],
                from_=m["from"],
                to=m["to"],
                ts=m["ts"],
                text=m["text"],
            )
            for m in messages
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get message statistics and analytics.

    Returns:
    - Total message count
    - Unique senders count
    - Top 10 senders by message count
    - First and last message timestamps
    """
    db = get_database()
    stats = db.get_stats()

    return StatsResponse(
        total_messages=stats["total_messages"],
        senders_count=stats["senders_count"],
        messages_per_sender=[
            SenderCount(from_=s["from"], count=s["count"])
            for s in stats["messages_per_sender"]
        ],
        first_message_ts=stats["first_message_ts"],
        last_message_ts=stats["last_message_ts"],
    )


@app.get("/health/live", response_model=HealthResponse)
async def liveness():
    """
    Liveness probe - returns 200 if the application is running.
    """
    return HealthResponse(status="ok")


@app.get(
    "/health/ready",
    response_model=HealthResponse,
    responses={503: {"model": ErrorResponse, "description": "Service not ready"}},
)
async def readiness():
    """
    Readiness probe - returns 200 only if:
    - Database is reachable and schema is applied
    - WEBHOOK_SECRET is configured
    """
    settings = get_settings()

    if not settings.webhook_secret:
        return JSONResponse(
            status_code=503,
            content={"detail": "WEBHOOK_SECRET not configured"},
        )

    db = get_database()
    if not db.is_ready():
        return JSONResponse(
            status_code=503,
            content={"detail": "Database not ready"},
        )

    return HealthResponse(status="ok")


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """
    Prometheus-style metrics endpoint.

    Exposes:
    - http_requests_total: Counter with path and status labels
    - webhook_requests_total: Counter with result label
    - request_latency_ms_bucket: Histogram of request latencies
    """
    metrics_collector = get_metrics()
    return PlainTextResponse(
        content=metrics_collector.export(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# Custom exception handler for validation errors
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom exception handler to ensure proper JSON responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

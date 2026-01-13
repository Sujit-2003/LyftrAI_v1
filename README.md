# Lyftr Webhook API

A production-style FastAPI service for ingesting WhatsApp-like messages with HMAC signature validation, structured logging, and Prometheus metrics.

## Features

- **Webhook Ingestion**: POST `/webhook` endpoint with HMAC-SHA256 signature validation
- **Idempotent Processing**: Duplicate messages are handled gracefully
- **Message Listing**: GET `/messages` with pagination and filtering
- **Analytics**: GET `/stats` for message statistics
- **Health Probes**: Kubernetes-style liveness and readiness endpoints
- **Prometheus Metrics**: `/metrics` endpoint with request counts and latency histograms
- **Structured Logging**: JSON-formatted logs with request context

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Make (optional, for convenience commands)

### Running the Application

```bash
# Set required environment variable
export WEBHOOK_SECRET="your-secret-key"

# Start the application
make up
# or: docker compose up -d --build

# View logs
make logs
# or: docker compose logs -f api

# Stop the application
make down
# or: docker compose down -v
```

The API will be available at `http://localhost:8000`.

## API Endpoints

### POST /webhook

Ingest inbound messages with HMAC signature validation.

**Request:**
```json
{
  "message_id": "m1",
  "from": "+919876543210",
  "to": "+14155550100",
  "ts": "2025-01-15T10:00:00Z",
  "text": "Hello"
}
```

**Headers:**
- `Content-Type: application/json`
- `X-Signature: <hex HMAC-SHA256 of raw request body>`

**Response:**
```json
{"status": "ok"}
```

**Status Codes:**
- `200`: Message accepted (new or duplicate)
- `401`: Invalid or missing signature
- `422`: Validation error

### GET /messages

List stored messages with pagination and filters.

**Query Parameters:**
- `limit` (int, 1-100, default: 50): Number of results
- `offset` (int, >= 0, default: 0): Skip this many results
- `from` (string): Filter by sender phone number
- `since` (string): ISO-8601 timestamp, return messages >= this time
- `q` (string): Case-insensitive text search

**Response:**
```json
{
  "data": [
    {
      "message_id": "m1",
      "from": "+919876543210",
      "to": "+14155550100",
      "ts": "2025-01-15T10:00:00Z",
      "text": "Hello"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### GET /stats

Get message analytics.

**Response:**
```json
{
  "total_messages": 123,
  "senders_count": 10,
  "messages_per_sender": [
    {"from": "+919876543210", "count": 50}
  ],
  "first_message_ts": "2025-01-10T09:00:00Z",
  "last_message_ts": "2025-01-15T10:00:00Z"
}
```

### GET /health/live

Liveness probe - always returns 200 if the app is running.

### GET /health/ready

Readiness probe - returns 200 only if:
- Database is reachable and schema is applied
- `WEBHOOK_SECRET` is configured

### GET /metrics

Prometheus-style metrics endpoint.

**Metrics exposed:**
- `http_requests_total{path, status}`: Counter of HTTP requests
- `webhook_requests_total{result}`: Counter of webhook outcomes (created, duplicate, invalid_signature, validation_error)
- `request_latency_ms_bucket{le}`: Histogram of request latencies

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WEBHOOK_SECRET` | Secret key for HMAC signature validation | *Required* |
| `DATABASE_URL` | SQLite database URL | `sqlite:////data/app.db` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |

## Design Decisions

### HMAC Verification

- Signatures are computed as `hex(HMAC-SHA256(secret, raw_body_bytes))`
- The raw request body is used to ensure byte-exact signature verification
- Constant-time comparison (`hmac.compare_digest`) prevents timing attacks
- Missing or invalid signatures return 401 with `{"detail": "invalid signature"}`

### Pagination Contract

- Results are ordered by `ts ASC, message_id ASC` for deterministic pagination
- `total` reflects the count of all records matching filters (ignoring pagination)
- `limit` and `offset` are echoed back in the response
- Maximum limit is 100 to prevent excessive response sizes

### Stats Implementation

- All aggregations are performed via SQL queries for efficiency
- `messages_per_sender` returns at most 10 entries, sorted by count descending
- Timestamps (`first_message_ts`, `last_message_ts`) are min/max of the `ts` field
- Returns `null` for timestamps when no messages exist

### Metrics

- Uses a simple in-memory implementation (thread-safe with locks)
- Latency histogram uses buckets: 10, 25, 50, 100, 250, 500, 1000, 2500, 5000ms
- Webhook outcomes tracked: created, duplicate, invalid_signature, validation_error

### Idempotency

- Messages are uniquely identified by `message_id` (PRIMARY KEY)
- Duplicate inserts return 200 without creating new rows
- Database integrity constraint ensures no duplicates at the storage level

## Project Structure

```
/app
  main.py           # FastAPI app, middleware, routes
  models.py         # Pydantic models for validation
  storage.py        # SQLite database operations
  logging_utils.py  # JSON structured logging
  metrics.py        # Prometheus metrics helpers
  config.py         # Environment configuration

/tests
  test_webhook.py   # Webhook endpoint tests
  test_messages.py  # Messages endpoint tests
  test_stats.py     # Stats endpoint tests
  test_health.py    # Health and metrics tests
  conftest.py       # Test fixtures

Dockerfile          # Multi-stage Docker build
docker-compose.yml  # Container orchestration
Makefile            # Convenience commands
README.md           # This file
```

## Running Tests

```bash
# Run tests locally
make test

# Or directly with pytest
WEBHOOK_SECRET=testsecret DATABASE_URL=sqlite:///test.db pytest tests/ -v
```

## Example Usage

```bash
# Set secret
export WEBHOOK_SECRET="testsecret"

# Start the service
make up

# Wait for startup
sleep 5

# Create a valid signature
BODY='{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'
SIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | cut -d' ' -f2)

# Send a message
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIG" \
  -d "$BODY"

# List messages
curl http://localhost:8000/messages

# Get stats
curl http://localhost:8000/stats

# Check health
curl http://localhost:8000/health/ready

# View metrics
curl http://localhost:8000/metrics
```

## Setup Used

VSCode + Claude Code (Anthropic CLI) for code generation and implementation guidance.

## License

This project is created as part of the Lyftr AI Backend Assignment.

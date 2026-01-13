"""
Prometheus-style metrics module.
"""
from collections import defaultdict
from threading import Lock
from typing import Dict, List


class MetricsCollector:
    """Simple Prometheus-compatible metrics collector."""

    def __init__(self):
        self._lock = Lock()
        # Counters
        self._http_requests: Dict[str, int] = defaultdict(int)
        self._webhook_requests: Dict[str, int] = defaultdict(int)
        # Histogram buckets for latency (in ms)
        self._latency_buckets = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, float("inf")]
        self._latency_counts: Dict[float, int] = {b: 0 for b in self._latency_buckets}
        self._latency_sum: float = 0.0
        self._latency_count: int = 0

    def inc_http_request(self, path: str, status: int) -> None:
        """Increment HTTP request counter."""
        with self._lock:
            key = f'{path}|{status}'
            self._http_requests[key] += 1

    def inc_webhook_request(self, result: str) -> None:
        """Increment webhook request counter."""
        with self._lock:
            self._webhook_requests[result] += 1

    def observe_latency(self, latency_ms: float) -> None:
        """Record a latency observation."""
        with self._lock:
            self._latency_sum += latency_ms
            self._latency_count += 1
            for bucket in self._latency_buckets:
                if latency_ms <= bucket:
                    self._latency_counts[bucket] += 1

    def export(self) -> str:
        """Export metrics in Prometheus text format."""
        lines: List[str] = []

        with self._lock:
            # HTTP requests counter
            lines.append("# HELP http_requests_total Total HTTP requests by path and status")
            lines.append("# TYPE http_requests_total counter")
            for key, count in sorted(self._http_requests.items()):
                path, status = key.rsplit("|", 1)
                lines.append(f'http_requests_total{{path="{path}",status="{status}"}} {count}')

            # Webhook requests counter
            lines.append("# HELP webhook_requests_total Total webhook requests by result")
            lines.append("# TYPE webhook_requests_total counter")
            for result, count in sorted(self._webhook_requests.items()):
                lines.append(f'webhook_requests_total{{result="{result}"}} {count}')

            # Latency histogram
            lines.append("# HELP request_latency_ms_bucket Request latency histogram in milliseconds")
            lines.append("# TYPE request_latency_ms_bucket histogram")

            cumulative = 0
            for bucket in self._latency_buckets:
                cumulative += self._latency_counts[bucket] - (
                    cumulative if bucket == float("inf") else 0
                )
                # Recalculate cumulative properly
                pass

            # Calculate cumulative counts for histogram
            cumulative = 0
            for bucket in self._latency_buckets:
                cumulative = sum(
                    self._latency_counts[b]
                    for b in self._latency_buckets
                    if b <= bucket
                )
                le = "+Inf" if bucket == float("inf") else str(int(bucket))
                lines.append(f'request_latency_ms_bucket{{le="{le}"}} {cumulative}')

            lines.append(f"request_latency_ms_sum {self._latency_sum:.2f}")
            lines.append(f"request_latency_ms_count {self._latency_count}")

        return "\n".join(lines) + "\n"


# Global metrics collector
_metrics: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics

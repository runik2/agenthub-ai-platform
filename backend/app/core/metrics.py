from __future__ import annotations

from collections import defaultdict
from threading import Lock


class Metrics:
    """Small dependency-free Prometheus registry for the API process."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: defaultdict[tuple[str, str], int] = defaultdict(int)
        self._errors: defaultdict[tuple[str, str], int] = defaultdict(int)
        self._duration_ms: defaultdict[str, float] = defaultdict(float)

    def observe_request(self, method: str, path: str, status: int, duration_ms: float) -> None:
        with self._lock:
            self._requests[(method, path)] += 1
            self._duration_ms[path] += duration_ms
            if status >= 500:
                self._errors[(method, path)] += 1

    def render(self) -> str:
        lines = [
            "# HELP agenthub_http_requests_total Total HTTP requests.",
            "# TYPE agenthub_http_requests_total counter",
        ]
        with self._lock:
            for (method, path), count in sorted(self._requests.items()):
                lines.append(
                    f'agenthub_http_requests_total{{method="{method}",path="{path}"}} {count}'
                )
            lines.extend(
                [
                    "# HELP agenthub_http_errors_total Total HTTP 5xx responses.",
                    "# TYPE agenthub_http_errors_total counter",
                ]
            )
            for (method, path), count in sorted(self._errors.items()):
                lines.append(
                    f'agenthub_http_errors_total{{method="{method}",path="{path}"}} {count}'
                )
            lines.extend(
                [
                    "# HELP agenthub_http_duration_ms_total Sum of request durations in milliseconds.",
                    "# TYPE agenthub_http_duration_ms_total counter",
                ]
            )
            for path, duration in sorted(self._duration_ms.items()):
                lines.append(f'agenthub_http_duration_ms_total{{path="{path}"}} {duration:.2f}')
        return "\n".join(lines) + "\n"


metrics = Metrics()

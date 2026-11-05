from __future__ import annotations

from collections import defaultdict
from threading import RLock


class Metrics:
    """Small dependency-free Prometheus registry for the API process."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._requests: defaultdict[tuple[str, str], int] = defaultdict(int)
        self._errors: defaultdict[tuple[str, str], int] = defaultdict(int)
        self._duration_ms: defaultdict[str, float] = defaultdict(float)
        self._workflow_steps: defaultdict[tuple[str, str], tuple[int, float]] = defaultdict(
            lambda: (0, 0.0)
        )

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
        lines.extend(
            [
                "# HELP agenthub_workflow_step_duration_ms_total Sum of workflow step durations.",
                "# TYPE agenthub_workflow_step_duration_ms_total counter",
                *self.render_workflow_steps(),
            ]
        )
        return "\n".join(lines) + "\n"

    def observe_workflow_step(self, workflow_id: str, step_type: str, duration_ms: float) -> None:
        with self._lock:
            count, total = self._workflow_steps[(workflow_id, step_type)]
            self._workflow_steps[(workflow_id, step_type)] = (count + 1, total + duration_ms)

    def render_workflow_steps(self) -> list[str]:
        with self._lock:
            return [
                "agenthub_workflow_step_duration_ms_total{"
                f'workflow_id="{workflow_id}",step_type="{step_type}"}} {total:.2f}'
                for (workflow_id, step_type), (_, total) in sorted(self._workflow_steps.items())
            ]


metrics = Metrics()

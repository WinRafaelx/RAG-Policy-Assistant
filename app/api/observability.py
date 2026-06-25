from collections import defaultdict, deque
from dataclasses import dataclass, field
from time import monotonic


@dataclass
class ServiceMetrics:
    requests_total: int = 0
    refusals_total: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    latency_ms_total: int = 0

    def record_request(self, latency_ms: int, refusal_reason: str | None) -> None:
        self.requests_total += 1
        self.latency_ms_total += latency_ms
        if refusal_reason:
            self.refusals_total[refusal_reason] += 1

    def reset(self) -> None:
        self.requests_total = 0
        self.refusals_total.clear()
        self.latency_ms_total = 0

    def render_prometheus(self, retrieval_backend: str) -> str:
        average_latency = (
            self.latency_ms_total / self.requests_total if self.requests_total else 0.0
        )
        lines = [
            "# HELP ttb_policy_assistant_requests_total Total ask requests.",
            "# TYPE ttb_policy_assistant_requests_total counter",
            f"ttb_policy_assistant_requests_total {self.requests_total}",
            "# HELP ttb_policy_assistant_refusals_total Total refusals by reason.",
            "# TYPE ttb_policy_assistant_refusals_total counter",
        ]
        for reason, count in sorted(self.refusals_total.items()):
            lines.append(f'ttb_policy_assistant_refusals_total{{reason="{reason}"}} {count}')
        lines.extend(
            [
                "# HELP ttb_policy_assistant_latency_ms_average Average ask latency in ms.",
                "# TYPE ttb_policy_assistant_latency_ms_average gauge",
                f"ttb_policy_assistant_latency_ms_average {average_latency:.2f}",
                "# HELP ttb_policy_assistant_retrieval_backend Active retrieval backend.",
                "# TYPE ttb_policy_assistant_retrieval_backend gauge",
                f'ttb_policy_assistant_retrieval_backend{{backend="{retrieval_backend}"}} 1',
            ]
        )
        return "\n".join(lines) + "\n"


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._requests_by_client: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, client_id: str, limit_per_minute: int) -> bool:
        if limit_per_minute <= 0:
            return True

        now = monotonic()
        window_start = now - 60
        requests = self._requests_by_client[client_id]
        while requests and requests[0] < window_start:
            requests.popleft()
        if len(requests) >= limit_per_minute:
            return False
        requests.append(now)
        return True

    def reset(self) -> None:
        self._requests_by_client.clear()

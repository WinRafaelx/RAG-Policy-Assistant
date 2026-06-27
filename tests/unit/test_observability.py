from app.api import observability
from app.api.observability import InMemoryRateLimiter, ServiceMetrics


def test_service_metrics_reset_clears_counts() -> None:
    metrics = ServiceMetrics()
    metrics.record_request(25, "prompt_injection")

    metrics.reset()

    assert metrics.requests_total == 0
    assert metrics.latency_ms_total == 0
    assert metrics.refusals_total == {}


def test_rate_limiter_allows_disabled_limits() -> None:
    limiter = InMemoryRateLimiter()

    assert limiter.allow("client-a", 0) is True
    assert limiter.allow("client-a", -1) is True


def test_rate_limiter_resets_after_window(monkeypatch) -> None:
    now = 100.0
    monkeypatch.setattr(observability, "monotonic", lambda: now)
    limiter = InMemoryRateLimiter()

    assert limiter.allow("client-a", 1) is True
    assert limiter.allow("client-a", 1) is False

    now = 161.0

    assert limiter.allow("client-a", 1) is True


def test_rate_limiter_reset_clears_client_state() -> None:
    limiter = InMemoryRateLimiter()
    assert limiter.allow("client-a", 1) is True
    assert limiter.allow("client-a", 1) is False

    limiter.reset()

    assert limiter.allow("client-a", 1) is True

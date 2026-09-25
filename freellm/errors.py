"""Typed exceptions raised by freellm backends.

The router (`router.py`) catches these to decide chain behavior: cooldown
duration, whether to disable a provider, or whether to fall through
immediately. Backends map raw HTTP/network failures into these types —
callers never see `httpx.HTTPStatusError` or similar leak out.
"""

from __future__ import annotations


class ProviderError(RuntimeError):
    """Base class for a single-provider call failure."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"{provider}: {message}")


class RateLimitedError(ProviderError):
    """HTTP 429. Router cools this provider:model down before retrying it."""

    def __init__(
        self,
        provider: str,
        message: str,
        *,
        retry_after_s: float | None = None,
        daily_exhausted: bool = False,
    ) -> None:
        self.retry_after_s = retry_after_s
        self.daily_exhausted = daily_exhausted
        super().__init__(provider, message)


class TransientProviderError(ProviderError):
    """408 / 5xx / timeout / network error. Worth retrying later, not now."""


class AuthError(ProviderError):
    """401 / 403. Router disables this provider for the rest of the process."""


class ProviderRequestError(ProviderError):
    """Any other 4xx. Not a quota or auth issue — likely a bad request shape."""


class AllProvidersExhaustedError(RuntimeError):
    """Raised when every provider in a modality's chain has been tried."""

    def __init__(self, chain_attempted: list[str]) -> None:
        self.chain_attempted = chain_attempted
        super().__init__(
            f"All free providers exhausted. Attempted: {', '.join(chain_attempted)}"
        )

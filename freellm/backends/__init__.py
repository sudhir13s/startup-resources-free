"""Backend implementations for freellm.

- `omniroute.OmniRouteBackend` — production via local OmniRoute proxy.
- `mock.MockBackend` — deterministic, no-network test backend.

Choose via `FREELLM_BACKEND` env var; resolved by `freellm.backend.get_backend()`.
"""

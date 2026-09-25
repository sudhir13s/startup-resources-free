"""Backend implementations for freellm.

- `openai_compat.OpenAICompatBackend` — production. Plain async httpx against
  OpenAI-compatible chat-completions endpoints (Groq, Gemini, OpenRouter,
  Cerebras, Mistral, SambaNova, NVIDIA NIM, Together, HF Router, GitHub
  Models). No Node sidecar, fits a 512 MB Render instance.
- `mock.MockBackend` — deterministic, no-network test backend.

Choose via `FREELLM_BACKEND` env var; resolved by `freellm.backend.get_backend()`.
"""

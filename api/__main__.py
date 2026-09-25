"""`python -m api` — run the service locally with uvicorn (reload off)."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=False)  # noqa: S104 - local/Render bind-all is intentional


if __name__ == "__main__":
    main()

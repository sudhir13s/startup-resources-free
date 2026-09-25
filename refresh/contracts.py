"""Contract between the API and the refresh runner."""

from __future__ import annotations

from typing import Protocol

from domain.runs import RefreshOptions, RunReport


class RefreshRunner(Protocol):
    async def run(self, report: RunReport) -> RunReport:
        """Execute a run already created in storage (status `running`).

        Must:
        - process `report.options` provider by provider, calling
          `repository.update_run(report)` after each provider so a restart
          loses at most one provider's work;
        - never raise for a single provider failure (record a `failed` outcome);
        - set the final `status` and `finished_at`, and return the report.
        The caller (API) pushes the database to the `data` branch afterwards.
        """
        ...


__all__ = ["RefreshOptions", "RefreshRunner", "RunReport"]

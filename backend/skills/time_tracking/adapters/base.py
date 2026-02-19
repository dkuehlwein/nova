"""Base class for client-specific Excel adapters."""

from datetime import datetime
from pathlib import Path


def _parse_date(date_str: str) -> datetime:
    """Parse a YYYY-MM-DD string into a date object."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


class BaseClientAdapter:
    """Base class for client Excel template adapters.

    Each subclass implements fill_template() to write time entries
    into that client's specific Excel template format.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id

    def filter_entries(
        self,
        entries: list[dict],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        """Filter entries by project and optionally by date range."""
        start = _parse_date(start_date) if start_date else None
        end = _parse_date(end_date) if end_date else None

        results = []
        for entry in entries:
            if entry.get("project_id") != self.project_id:
                continue
            entry_date = _parse_date(entry["date"])
            if start and entry_date < start:
                continue
            if end and entry_date > end:
                continue
            results.append(entry)

        return results

    def fill_template(
        self,
        entries: list[dict],
        template_path: Path,
        output_path: Path,
    ) -> dict:
        """Fill a client's Excel template with time entries.

        Must be implemented by each client-specific adapter.
        """
        raise NotImplementedError(
            f"Adapter for {self.project_id} must implement fill_template()"
        )

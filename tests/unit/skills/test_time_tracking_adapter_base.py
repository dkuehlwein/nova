"""Tests for client adapter base class."""

import pytest

from skills.time_tracking.adapters.base import BaseClientAdapter


class TestBaseAdapter:
    def test_filter_entries_by_project(self):
        """Base adapter filters entries by project_id."""
        adapter = BaseClientAdapter(project_id="PRJA-001")
        entries = [
            {"date": "2026-02-03", "project_id": "PRJA-001", "hours": 4.0},
            {"date": "2026-02-03", "project_id": "INT-001", "hours": 2.0},
        ]
        filtered = adapter.filter_entries(entries)
        assert len(filtered) == 1
        assert filtered[0]["project_id"] == "PRJA-001"

    def test_filter_entries_by_date_range(self):
        """Base adapter filters entries by date range."""
        adapter = BaseClientAdapter(project_id="PRJA-001")
        entries = [
            {"date": "2026-02-03", "project_id": "PRJA-001", "hours": 4.0},
            {"date": "2026-02-10", "project_id": "PRJA-001", "hours": 3.0},
        ]
        filtered = adapter.filter_entries(entries, start_date="2026-02-01", end_date="2026-02-05")
        assert len(filtered) == 1

    def test_fill_template_not_implemented(self, tmp_path):
        """Base adapter's fill_template raises NotImplementedError."""
        adapter = BaseClientAdapter(project_id="PRJA-001")
        with pytest.raises(NotImplementedError):
            adapter.fill_template([], template_path=tmp_path / "template.xlsx", output_path=tmp_path / "output.xlsx")

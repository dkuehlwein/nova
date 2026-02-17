"""Tests for time tracking master Excel operations."""

import pytest

from skills.time_tracking.excel_manager import log_entries, read_entries


class TestLogEntries:
    """Tests for writing time entries to the master Excel."""

    def test_log_single_entry(self, tmp_path):
        """Writing a single entry creates the Excel file with correct data."""
        entry = {
            "date": "2026-02-03",
            "project": "ClientA - Dev",
            "project_id": "PRJA-001",
            "hours": 4.0,
            "description": "Feature X",
        }

        result = log_entries([entry], timesheet_dir=str(tmp_path))
        assert result["success"] is True
        assert result["file"] == "2026-02-timesheet.xlsx"
        assert result["entries_written"] == 1

        entries = read_entries("2026-02-03", "2026-02-03", timesheet_dir=str(tmp_path))
        assert len(entries) == 1
        assert entries[0]["project_id"] == "PRJA-001"
        assert entries[0]["hours"] == 4.0

    def test_log_entry_with_start_end_times(self, tmp_path):
        """Entries can optionally include start and end times."""
        entry = {
            "date": "2026-02-03",
            "project": "ClientA - Dev",
            "project_id": "PRJA-001",
            "start": "09:00",
            "end": "13:00",
            "hours": 4.0,
            "description": "Feature X",
        }

        log_entries([entry], timesheet_dir=str(tmp_path))
        entries = read_entries("2026-02-03", "2026-02-03", timesheet_dir=str(tmp_path))
        assert entries[0]["start"] == "09:00"
        assert entries[0]["end"] == "13:00"

    def test_log_multiple_entries_appends(self, tmp_path):
        """Multiple calls append rows, not overwrite."""
        log_entries(
            [{"date": "2026-02-03", "project": "A", "project_id": "A-001", "hours": 4.0}],
            timesheet_dir=str(tmp_path),
        )
        log_entries(
            [{"date": "2026-02-03", "project": "B", "project_id": "B-001", "hours": 3.0}],
            timesheet_dir=str(tmp_path),
        )

        entries = read_entries("2026-02-03", "2026-02-03", timesheet_dir=str(tmp_path))
        assert len(entries) == 2

    def test_creates_new_file_per_month(self, tmp_path):
        """Entries in different months go to different files."""
        log_entries(
            [{"date": "2026-02-03", "project": "A", "project_id": "A-001", "hours": 4.0}],
            timesheet_dir=str(tmp_path),
        )
        log_entries(
            [{"date": "2026-03-03", "project": "A", "project_id": "A-001", "hours": 4.0}],
            timesheet_dir=str(tmp_path),
        )

        assert (tmp_path / "2026-02-timesheet.xlsx").exists()
        assert (tmp_path / "2026-03-timesheet.xlsx").exists()


class TestReadEntries:
    """Tests for reading time entries from master Excel."""

    def test_read_date_range(self, tmp_path):
        """Reads only entries within the specified date range."""
        entries = [
            {"date": "2026-02-03", "project": "A", "project_id": "A-001", "hours": 4.0},
            {"date": "2026-02-04", "project": "B", "project_id": "B-001", "hours": 3.0},
            {"date": "2026-02-05", "project": "A", "project_id": "A-001", "hours": 5.0},
        ]
        log_entries(entries, timesheet_dir=str(tmp_path))

        result = read_entries("2026-02-03", "2026-02-04", timesheet_dir=str(tmp_path))
        assert len(result) == 2

    def test_read_nonexistent_month_returns_empty(self, tmp_path):
        """Reading from a month with no file returns empty list."""
        result = read_entries("2026-02-01", "2026-02-28", timesheet_dir=str(tmp_path))
        assert result == []

    def test_read_entries_by_project(self, tmp_path):
        """Can filter entries by project_id."""
        entries = [
            {"date": "2026-02-03", "project": "A", "project_id": "A-001", "hours": 4.0},
            {"date": "2026-02-03", "project": "B", "project_id": "B-001", "hours": 3.0},
        ]
        log_entries(entries, timesheet_dir=str(tmp_path))

        result = read_entries(
            "2026-02-01", "2026-02-28",
            timesheet_dir=str(tmp_path),
            project_id="A-001",
        )
        assert len(result) == 1
        assert result[0]["project_id"] == "A-001"

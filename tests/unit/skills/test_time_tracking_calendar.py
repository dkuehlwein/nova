"""Tests for calendar-based hour suggestions."""

import json

import pytest
from unittest.mock import AsyncMock, patch


class TestSuggestHoursFromCalendar:
    @pytest.mark.asyncio
    async def test_suggests_hours_from_calendar_events(self, mock_config):
        """Transforms calendar events into time entry suggestions."""
        from skills.time_tracking.tools import suggest_hours_from_calendar

        mock_events = [
            {
                "subject": "ClientA Sprint Planning",
                "start": {"dateTime": "2026-02-03T09:00:00"},
                "end": {"dateTime": "2026-02-03T10:00:00"},
            },
            {
                "subject": "Internal Team Standup",
                "start": {"dateTime": "2026-02-03T10:30:00"},
                "end": {"dateTime": "2026-02-03T11:00:00"},
            },
        ]

        with patch(
            "skills.time_tracking.tools._get_calendar_events",
            new_callable=AsyncMock,
        ) as mock_cal:
            mock_cal.return_value = mock_events

            result_str = await suggest_hours_from_calendar.ainvoke(
                {"target_date": "2026-02-03"}
            )
            result = json.loads(result_str)

            assert result["success"] is True
            assert result["date"] == "2026-02-03"
            assert len(result["suggestions"]) == 2
            assert "next_action" in result

            # Check suggestion structure
            first = result["suggestions"][0]
            assert "subject" in first
            assert "hours" in first
            assert "start" in first
            assert "end" in first
            assert first["hours"] == 1.0  # 09:00 to 10:00

            second = result["suggestions"][1]
            assert second["hours"] == 0.5  # 10:30 to 11:00

    @pytest.mark.asyncio
    async def test_handles_no_calendar_events(self, mock_config):
        """Returns success with empty suggestions when no events are found.

        This also covers the MCP-unavailable case: _get_calendar_events catches
        all MCP errors internally and returns [], which produces the same result.
        """
        from skills.time_tracking.tools import suggest_hours_from_calendar

        with patch(
            "skills.time_tracking.tools._get_calendar_events",
            new_callable=AsyncMock,
        ) as mock_cal:
            mock_cal.return_value = []

            result_str = await suggest_hours_from_calendar.ainvoke(
                {"target_date": "2026-02-03"}
            )
            result = json.loads(result_str)

            assert result["success"] is True
            assert result["suggestions"] == []
            assert result["date"] == "2026-02-03"
            assert "next_action" in result

    @pytest.mark.asyncio
    async def test_matches_events_to_configured_projects(self, mock_config):
        """Events matching configured project names get a project_id in the suggestion."""
        from skills.time_tracking.tools import suggest_hours_from_calendar

        mock_events = [
            {
                "subject": "ClientA - Development review",
                "start": {"dateTime": "2026-02-03T09:00:00"},
                "end": {"dateTime": "2026-02-03T11:00:00"},
            },
            {
                "subject": "Random external call",
                "start": {"dateTime": "2026-02-03T14:00:00"},
                "end": {"dateTime": "2026-02-03T15:00:00"},
            },
        ]

        with patch(
            "skills.time_tracking.tools._get_calendar_events",
            new_callable=AsyncMock,
        ) as mock_cal:
            mock_cal.return_value = mock_events

            result_str = await suggest_hours_from_calendar.ainvoke(
                {"target_date": "2026-02-03"}
            )
            result = json.loads(result_str)

            assert result["success"] is True
            assert len(result["suggestions"]) == 2

            # First event should match "ClientA - Development" project
            first = result["suggestions"][0]
            assert first["project_id"] == "PRJA-001"
            assert first["project"] == "ClientA - Development"

            # Second event should have no project match
            second = result["suggestions"][1]
            assert second.get("project_id") is None

    @pytest.mark.asyncio
    async def test_defaults_to_today_when_no_date(self, mock_config):
        """Uses today's date when target_date is empty."""
        from skills.time_tracking.tools import suggest_hours_from_calendar

        with patch(
            "skills.time_tracking.tools._get_calendar_events",
            new_callable=AsyncMock,
        ) as mock_cal:
            mock_cal.return_value = []

            result_str = await suggest_hours_from_calendar.ainvoke(
                {"target_date": ""}
            )
            result = json.loads(result_str)

            assert result["success"] is True
            # Should have called _get_calendar_events with today's date
            called_date = mock_cal.call_args[0][0]
            assert len(called_date) == 10  # YYYY-MM-DD format
            assert result["date"] == called_date

    @pytest.mark.asyncio
    async def test_filters_out_unparseable_events(self, mock_config):
        """Events with no valid time data are excluded from suggestions."""
        from skills.time_tracking.tools import suggest_hours_from_calendar

        mock_events = [
            {
                "subject": "Valid meeting",
                "start": {"dateTime": "2026-02-03T09:00:00"},
                "end": {"dateTime": "2026-02-03T10:00:00"},
            },
            {
                "subject": "All-day event with no times",
                # Missing start/end dateTime fields
            },
            {
                "subject": "Broken event",
                "start": {"dateTime": "not-a-date"},
                "end": {"dateTime": "also-not-a-date"},
            },
        ]

        with patch(
            "skills.time_tracking.tools._get_calendar_events",
            new_callable=AsyncMock,
        ) as mock_cal:
            mock_cal.return_value = mock_events

            result_str = await suggest_hours_from_calendar.ainvoke(
                {"target_date": "2026-02-03"}
            )
            result = json.loads(result_str)

            assert result["success"] is True
            assert result["count"] == 1
            assert len(result["suggestions"]) == 1
            assert result["suggestions"][0]["subject"] == "Valid meeting"

    @pytest.mark.asyncio
    async def test_next_action_differs_for_empty_suggestions(self, mock_config):
        """next_action tells the user to provide hours manually when no events found."""
        from skills.time_tracking.tools import suggest_hours_from_calendar

        with patch(
            "skills.time_tracking.tools._get_calendar_events",
            new_callable=AsyncMock,
        ) as mock_cal:
            mock_cal.return_value = []

            result_str = await suggest_hours_from_calendar.ainvoke(
                {"target_date": "2026-02-03"}
            )
            result = json.loads(result_str)

            assert "manually" in result["next_action"].lower()
            assert "log_hours" in result["next_action"]

    @pytest.mark.asyncio
    async def test_next_action_for_non_empty_suggestions(self, mock_config):
        """next_action asks user to review suggestions when events are found."""
        from skills.time_tracking.tools import suggest_hours_from_calendar

        mock_events = [
            {
                "subject": "Meeting",
                "start": {"dateTime": "2026-02-03T09:00:00"},
                "end": {"dateTime": "2026-02-03T10:00:00"},
            },
        ]

        with patch(
            "skills.time_tracking.tools._get_calendar_events",
            new_callable=AsyncMock,
        ) as mock_cal:
            mock_cal.return_value = mock_events

            result_str = await suggest_hours_from_calendar.ainvoke(
                {"target_date": "2026-02-03"}
            )
            result = json.loads(result_str)

            assert "review" in result["next_action"].lower()
            assert "log_hours" in result["next_action"]


class TestNormalizeCalendarResponse:
    def test_extracts_value_key_from_dict(self):
        """Extracts the 'value' list from a Graph API-style response."""
        from skills.time_tracking.tools import _normalize_calendar_response

        events = [{"subject": "A"}]
        assert _normalize_calendar_response({"value": events}) == events

    def test_wraps_single_event_dict(self):
        """Wraps a single event dict (with 'subject' key) in a list."""
        from skills.time_tracking.tools import _normalize_calendar_response

        event = {"subject": "Solo Event"}
        assert _normalize_calendar_response(event) == [event]

    def test_returns_list_as_is(self):
        """Passes through a response that is already a list."""
        from skills.time_tracking.tools import _normalize_calendar_response

        events = [{"subject": "A"}, {"subject": "B"}]
        assert _normalize_calendar_response(events) == events

    def test_returns_empty_for_unknown_format(self):
        """Returns empty list for unexpected response types."""
        from skills.time_tracking.tools import _normalize_calendar_response

        assert _normalize_calendar_response(42) == []
        assert _normalize_calendar_response({"unrelated": "data"}) == []


class TestParseEventTimes:
    def test_parses_valid_start_and_end(self):
        """Extracts formatted times and duration from valid ISO datetimes."""
        from skills.time_tracking.tools import _parse_event_times

        event = {
            "start": {"dateTime": "2026-02-03T09:00:00"},
            "end": {"dateTime": "2026-02-03T10:30:00"},
        }
        start, end, hours = _parse_event_times(event)
        assert start == "09:00"
        assert end == "10:30"
        assert hours == 1.5

    def test_returns_defaults_for_missing_times(self):
        """Returns empty strings and zero hours when times are absent."""
        from skills.time_tracking.tools import _parse_event_times

        assert _parse_event_times({}) == ("", "", 0.0)
        assert _parse_event_times({"start": {}}) == ("", "", 0.0)

    def test_handles_mixed_timezone_datetimes(self):
        """Handles events where one datetime has timezone info and the other does not."""
        from skills.time_tracking.tools import _parse_event_times

        event = {
            "start": {"dateTime": "2026-02-03T09:00:00+01:00"},
            "end": {"dateTime": "2026-02-03T11:00:00"},
        }
        start, end, hours = _parse_event_times(event)
        assert start == "09:00"
        assert end == "11:00"
        assert hours == 2.0

    def test_handles_both_timezone_aware_datetimes(self):
        """Handles events where both datetimes have timezone info."""
        from skills.time_tracking.tools import _parse_event_times

        event = {
            "start": {"dateTime": "2026-02-03T09:00:00+01:00"},
            "end": {"dateTime": "2026-02-03T11:00:00+01:00"},
        }
        start, end, hours = _parse_event_times(event)
        assert start == "09:00"
        assert end == "11:00"
        assert hours == 2.0


class TestMatchProject:
    def test_matches_by_case_insensitive_substring(self):
        """Matches project name as case-insensitive substring of subject."""
        from skills.time_tracking.tools import _match_project

        projects = [{"name": "Alpha", "id": "A-1"}]
        assert _match_project("Weekly Alpha sync", projects) == projects[0]
        assert _match_project("weekly alpha sync", projects) == projects[0]

    def test_returns_none_for_no_match(self):
        """Returns None when no project name appears in the subject."""
        from skills.time_tracking.tools import _match_project

        projects = [{"name": "Alpha", "id": "A-1"}]
        assert _match_project("Unrelated meeting", projects) is None

    def test_empty_project_name_does_not_match(self):
        """Projects with empty or missing names do not match any subject."""
        from skills.time_tracking.tools import _match_project

        projects = [
            {"name": "", "id": "EMPTY-1"},
            {"name": "Alpha", "id": "A-1"},
        ]
        # Empty name should be skipped; should match Alpha
        result = _match_project("Alpha standup", projects)
        assert result["id"] == "A-1"

    def test_missing_name_key_does_not_match(self):
        """Projects missing the 'name' key entirely do not match."""
        from skills.time_tracking.tools import _match_project

        projects = [{"id": "NO-NAME"}]
        assert _match_project("Anything at all", projects) is None


class TestGetCalendarEvents:
    @pytest.mark.asyncio
    async def test_fetches_events_via_mcp(self):
        """_get_calendar_events calls MCP server and returns events."""
        from skills.time_tracking.tools import _get_calendar_events

        mock_response = json.dumps({
            "value": [
                {
                    "subject": "Test Meeting",
                    "start": {"dateTime": "2026-02-03T09:00:00"},
                    "end": {"dateTime": "2026-02-03T10:00:00"},
                }
            ]
        })

        with patch("mcp_client.mcp_manager") as mock_mcp:
            mock_mcp.call_mcp_tool = AsyncMock(return_value=mock_response)

            events = await _get_calendar_events("2026-02-03")

            assert len(events) == 1
            assert events[0]["subject"] == "Test Meeting"
            mock_mcp.call_mcp_tool.assert_called_once_with(
                server_name="ms_graph",
                tool_name="list_calendar_events",
                arguments={
                    "start_date": "2026-02-03T00:00:00",
                    "end_date": "2026-02-03T23:59:59",
                },
            )

    @pytest.mark.asyncio
    async def test_returns_empty_on_mcp_failure(self):
        """_get_calendar_events returns empty list when MCP call fails."""
        from skills.time_tracking.tools import _get_calendar_events

        with patch("mcp_client.mcp_manager") as mock_mcp:
            mock_mcp.call_mcp_tool = AsyncMock(
                side_effect=Exception("Connection refused")
            )

            events = await _get_calendar_events("2026-02-03")
            assert events == []

    @pytest.mark.asyncio
    async def test_handles_list_response_without_value_key(self):
        """_get_calendar_events handles responses that are already a list."""
        from skills.time_tracking.tools import _get_calendar_events

        mock_response = [
            {
                "subject": "Direct List Event",
                "start": {"dateTime": "2026-02-03T09:00:00"},
                "end": {"dateTime": "2026-02-03T10:00:00"},
            }
        ]

        with patch("mcp_client.mcp_manager") as mock_mcp:
            mock_mcp.call_mcp_tool = AsyncMock(return_value=mock_response)

            events = await _get_calendar_events("2026-02-03")
            assert len(events) == 1
            assert events[0]["subject"] == "Direct List Event"

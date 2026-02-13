"""
Chat Service Unit Tests

Tests for the ChatService class that handles chat streaming and LangGraph interaction.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.services.chat_service import ChatService, chat_service
from backend.models.chat import ChatMessage, ChatRequest
from backend.utils.langgraph_utils import create_langgraph_config


@pytest.fixture
def service():
    """Create a ChatService instance for testing."""
    return ChatService()


class TestMessageConversion:
    """Test message conversion between Pydantic and LangChain formats."""

    def test_convert_user_messages(self, service):
        """Test converting user messages to LangChain format."""
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="user", content="How are you?"),
        ]

        result = service.convert_messages_to_langchain(messages)

        assert len(result) == 2
        assert isinstance(result[0], HumanMessage)
        assert isinstance(result[1], HumanMessage)
        assert result[0].content == "Hello"
        assert result[1].content == "How are you?"

    def test_convert_assistant_messages(self, service):
        """Test converting assistant messages to LangChain format."""
        messages = [
            ChatMessage(role="assistant", content="I am doing well!"),
        ]

        result = service.convert_messages_to_langchain(messages)

        assert len(result) == 1
        assert isinstance(result[0], AIMessage)
        assert result[0].content == "I am doing well!"

    def test_convert_mixed_messages(self, service):
        """Test converting a mix of user and assistant messages."""
        messages = [
            ChatMessage(role="user", content="Hi"),
            ChatMessage(role="assistant", content="Hello!"),
            ChatMessage(role="user", content="What's the weather?"),
        ]

        result = service.convert_messages_to_langchain(messages)

        assert len(result) == 3
        assert isinstance(result[0], HumanMessage)
        assert isinstance(result[1], AIMessage)
        assert isinstance(result[2], HumanMessage)

    def test_convert_empty_messages(self, service):
        """Test converting empty message list."""
        result = service.convert_messages_to_langchain([])
        assert result == []


class TestConfigCreation:
    """Test LangGraph configuration creation via utility function."""

    def test_create_config_with_thread_id(self):
        """Test creating config with provided thread ID."""
        config = create_langgraph_config("test-thread-123")

        assert config == {"configurable": {"thread_id": "test-thread-123"}}

    def test_create_config_generates_thread_id(self):
        """Test that config generates thread ID when not provided."""
        config = create_langgraph_config()

        assert "configurable" in config
        assert "thread_id" in config["configurable"]
        assert config["configurable"]["thread_id"].startswith("chat-")

    def test_create_config_none_thread_id(self):
        """Test creating config with explicit None generates new ID."""
        config = create_langgraph_config(None)

        assert "configurable" in config
        assert config["configurable"]["thread_id"].startswith("chat-")


class TestFirstTurnDetection:
    """Test first turn detection in conversations."""

    @pytest.mark.asyncio
    async def test_is_first_turn_no_state(self, service):
        """Test that no state means first turn."""
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = None

        result = await service.is_first_turn("test-thread", mock_checkpointer)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_first_turn_empty_messages(self, service):
        """Test that empty messages means first turn."""
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = {
            "channel_values": {"messages": []}
        }

        result = await service.is_first_turn("test-thread", mock_checkpointer)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_not_first_turn_with_messages(self, service):
        """Test that existing messages means not first turn."""
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = {
            "channel_values": {"messages": [HumanMessage(content="Hello")]}
        }

        result = await service.is_first_turn("test-thread", mock_checkpointer)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_first_turn_error_handling(self, service):
        """Test that errors default to not first turn (safe behavior)."""
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.side_effect = Exception("Database error")

        result = await service.is_first_turn("test-thread", mock_checkpointer)

        # Should return False (not first turn) on error for safety
        assert result is False


class TestMemoryInjection:
    """Test memory context injection for first turn.

    Note: These tests verify the structure of memory injection messages
    without actually calling the real memory service (which requires Neo4j).
    The error handling test verifies graceful degradation.
    """

    def test_memory_tool_message_structure(self):
        """Test that memory tool messages have correct structure."""
        # Create sample messages like inject_memory_context would return
        ai_tool_call = AIMessage(
            content="Before answering you, let me search my memory...",
            tool_calls=[
                {
                    "name": "search_memory",
                    "args": {"query": "test"},
                    "id": "memory_search_auto",
                    "type": "tool_call",
                }
            ],
        )
        tool_result = ToolMessage(
            content="Found 2 relevant memories:\n- Fact 1\n- Fact 2",
            tool_call_id="memory_search_auto"
        )

        # Verify structure
        assert ai_tool_call.content is not None
        assert len(ai_tool_call.tool_calls) == 1
        assert ai_tool_call.tool_calls[0]["name"] == "search_memory"
        assert tool_result.tool_call_id == "memory_search_auto"

    @pytest.mark.asyncio
    async def test_inject_memory_context_returns_messages_or_empty(self, service):
        """Test memory injection returns proper messages or empty list on error."""
        result = await service.inject_memory_context("Hello")

        # Should return either messages (if Neo4j is running) or empty list (if not)
        if result:
            # If we got results, verify structure
            assert len(result) == 2
            assert isinstance(result[0], AIMessage)
            assert isinstance(result[1], ToolMessage)
        else:
            # Empty list is also valid (error case)
            assert result == []


class TestCheckInterrupts:
    """Test interrupt/escalation checking."""

    @pytest.mark.asyncio
    async def test_check_interrupts_no_interrupts(self, service):
        """Test when there are no pending interrupts."""
        mock_state = MagicMock()
        mock_state.interrupts = []
        mock_state.values = {"messages": []}
        mock_state.next = []

        mock_agent = AsyncMock()
        mock_agent.aget_state.return_value = mock_state

        result = await service.check_interrupts("test-thread", mock_agent)

        assert result is None

    @pytest.mark.asyncio
    async def test_check_interrupts_user_question(self, service):
        """Test detecting user question interrupt."""
        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "type": "user_question",
            "question": "What color should the button be?",
            "instructions": "Please choose a color"
        }

        mock_state = MagicMock()
        mock_state.interrupts = [mock_interrupt]
        mock_state.values = {"messages": []}
        mock_state.next = []

        mock_agent = AsyncMock()
        mock_agent.aget_state.return_value = mock_state

        result = await service.check_interrupts("test-thread", mock_agent)

        assert result is not None
        assert result["type"] == "user_question"
        assert "color" in result["question"]

    @pytest.mark.asyncio
    async def test_check_interrupts_tool_approval(self, service):
        """Test detecting tool approval interrupt."""
        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "type": "tool_approval_request",
            "tool_name": "send_email",
            "tool_args": {"to": "user@example.com"},
            "tool_call_id": "call-123"
        }

        mock_state = MagicMock()
        mock_state.interrupts = [mock_interrupt]
        mock_state.values = {"messages": []}
        mock_state.next = []

        mock_agent = AsyncMock()
        mock_agent.aget_state.return_value = mock_state

        result = await service.check_interrupts("test-thread", mock_agent)

        assert result is not None
        assert result["type"] == "tool_approval_request"
        assert result["tool_name"] == "send_email"


    @pytest.mark.asyncio
    async def test_check_interrupts_tool_approval_resolves_tool_call_id_from_messages(self, service):
        """Test that tool_call_id is resolved from messages when not in interrupt value.

        This is the real-world case: the interrupt value from tool_approval_helper
        does NOT include tool_call_id, so check_interrupts must find the matching
        tool call in the message history by tool name.
        """
        # Interrupt value without tool_call_id (matches what tool_approval_helper sends)
        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "type": "tool_approval_request",
            "tool_name": "ms_graph_send_email",
            "tool_args": {"recipients": ["user@example.com"], "subject": "Hi"},
            "question": "Nova wants to use the tool: ms_graph_send_email",
            "instructions": "Please approve or deny this tool action to continue.",
        }

        # Message history contains the AI tool call with the real tool_call_id
        ai_msg = AIMessage(
            content="I'll send that email for you.",
            tool_calls=[{
                "name": "ms_graph_send_email",
                "args": {"recipients": ["user@example.com"], "subject": "Hi"},
                "id": "call_abc123",
                "type": "tool_call",
            }],
        )

        mock_state = MagicMock()
        mock_state.interrupts = [mock_interrupt]
        mock_state.values = {"messages": [HumanMessage(content="Send email"), ai_msg]}
        mock_state.next = []

        mock_agent = AsyncMock()
        mock_agent.aget_state.return_value = mock_state

        result = await service.check_interrupts("test-thread", mock_agent)

        assert result is not None
        assert result["type"] == "tool_approval_request"
        assert result["tool_name"] == "ms_graph_send_email"
        assert result["tool_call_id"] == "call_abc123"

    @pytest.mark.asyncio
    async def test_check_interrupts_tool_approval_no_matching_tool_call(self, service):
        """Test that tool_call_id is None when tool name not found in messages."""
        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "type": "tool_approval_request",
            "tool_name": "ms_graph_send_email",
            "tool_args": {},
        }

        mock_state = MagicMock()
        mock_state.interrupts = [mock_interrupt]
        mock_state.values = {"messages": [HumanMessage(content="Send email")]}
        mock_state.next = []

        mock_agent = AsyncMock()
        mock_agent.aget_state.return_value = mock_state

        result = await service.check_interrupts("test-thread", mock_agent)

        assert result is not None
        assert result["type"] == "tool_approval_request"
        assert result["tool_call_id"] is None

    @pytest.mark.asyncio
    async def test_check_interrupts_disambiguates_duplicate_tool_calls(self, service):
        """When the same tool appears multiple times, match by args to find the right one.

        Simulates: two ms_graph_send_email tool calls in one AIMessage with different
        args. The interrupt's tool_args should select the correct tool_call_id.
        """
        tool_name = "ms_graph_send_email"
        first_args = {"recipients": ["alice@example.com"], "subject": "First email"}
        second_args = {"recipients": ["bob@example.com"], "subject": "Second email"}

        # Interrupt targets the second tool call
        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "type": "tool_approval_request",
            "tool_name": tool_name,
            "tool_args": second_args,
        }

        # AIMessage has both tool calls
        ai_msg = MagicMock()
        ai_msg.tool_calls = [
            {"name": tool_name, "args": first_args, "id": "call_first"},
            {"name": tool_name, "args": second_args, "id": "call_second"},
        ]

        mock_state = MagicMock()
        mock_state.interrupts = [mock_interrupt]
        mock_state.values = {"messages": [HumanMessage(content="Send emails"), ai_msg]}
        mock_state.next = []

        mock_agent = AsyncMock()
        mock_agent.aget_state.return_value = mock_state

        result = await service.check_interrupts("test-thread", mock_agent)

        assert result is not None
        assert result["type"] == "tool_approval_request"
        assert result["tool_name"] == tool_name
        # Must resolve to "call_second" (matching args), NOT "call_first"
        assert result["tool_call_id"] == "call_second"

    @pytest.mark.asyncio
    async def test_check_interrupts_falls_back_to_name_when_args_mismatch(self, service):
        """When tool_args don't match any tool call exactly, fall back to name-only match."""
        tool_name = "ms_graph_send_email"
        interrupt_args = {"recipients": ["user@example.com"]}
        # Tool call has different args (extra field)
        tool_call_args = {"recipients": ["user@example.com"], "body": "Hi there"}

        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "type": "tool_approval_request",
            "tool_name": tool_name,
            "tool_args": interrupt_args,
        }

        ai_msg = MagicMock()
        ai_msg.tool_calls = [
            {"name": tool_name, "args": tool_call_args, "id": "call_only"},
        ]

        mock_state = MagicMock()
        mock_state.interrupts = [mock_interrupt]
        mock_state.values = {"messages": [HumanMessage(content="Send email"), ai_msg]}
        mock_state.next = []

        mock_agent = AsyncMock()
        mock_agent.aget_state.return_value = mock_state

        result = await service.check_interrupts("test-thread", mock_agent)

        assert result is not None
        assert result["type"] == "tool_approval_request"
        # Falls back to name-only match since args don't match exactly
        assert result["tool_call_id"] == "call_only"


class TestResumeInterruptImport:
    """Test that resume_interrupt uses a valid import for Command.

    Regression test for NOV-116: the original code imported Command from
    'langgraph.graph.graph' which does not exist in langgraph >= 1.0.
    The correct import is 'from langgraph.types import Command'.
    """

    @pytest.mark.asyncio
    async def test_resume_interrupt_does_not_raise_import_error(self, service):
        """resume_interrupt must not fail with ModuleNotFoundError on Command import.

        This test does NOT mock 'langgraph.graph.graph' so the real import runs.
        Before the fix, this raises:
            ModuleNotFoundError: No module named 'langgraph.graph.graph'
        """
        mock_agent = AsyncMock()
        mock_agent.aupdate_state = AsyncMock()
        mock_agent.ainvoke = AsyncMock()

        with patch("services.chat_metadata_service.chat_metadata_service") as mock_meta_svc:
            mock_meta_svc.record_approval = AsyncMock()

            # Should NOT raise ModuleNotFoundError
            result = await service.resume_interrupt(
                "test-thread",
                {"type": "approve", "tool_call_id": "call_abc"},
                mock_agent,
            )

        assert result["success"] is True


class TestResumeInterrupt:
    """Test interrupt resumption and approval persistence."""

    @pytest.mark.asyncio
    async def test_uses_tool_call_id_from_request_body(self, service):
        """Frontend sends tool_call_id with approval — backend uses it directly."""
        mock_agent = AsyncMock()
        mock_agent.aupdate_state = AsyncMock()
        mock_agent.ainvoke = AsyncMock()

        with patch.object(service, "check_interrupts", new_callable=AsyncMock) as mock_check, \
             patch("services.chat_metadata_service.chat_metadata_service") as mock_meta_svc:
            mock_check.return_value = {
                "type": "tool_approval_request",
                "tool_name": "ms_graph-send_email",
                "tool_call_id": None,
            }
            mock_meta_svc.record_approval = AsyncMock()

            result = await service.resume_interrupt(
                "test-thread",
                {"type": "approve", "tool_call_id": "call_from_frontend"},
                mock_agent,
            )

        assert result["success"] is True
        mock_meta_svc.record_approval.assert_awaited_once_with("test-thread", "call_from_frontend")
        # check_interrupts should NOT be called when request has tool_call_id
        mock_check.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_records_approval_when_check_interrupts_fails(self, service):
        """Approval is recorded even when check_interrupts returns None entirely."""
        mock_agent = AsyncMock()
        mock_agent.aupdate_state = AsyncMock()
        mock_agent.ainvoke = AsyncMock()

        with patch.object(service, "check_interrupts", new_callable=AsyncMock) as mock_check, \
             patch("services.chat_metadata_service.chat_metadata_service") as mock_meta_svc:
            mock_check.return_value = None
            mock_meta_svc.record_approval = AsyncMock()

            result = await service.resume_interrupt(
                "test-thread",
                {"type": "approve", "tool_call_id": "call_from_frontend"},
                mock_agent,
            )

        assert result["success"] is True
        mock_meta_svc.record_approval.assert_awaited_once_with("test-thread", "call_from_frontend")

    @pytest.mark.asyncio
    async def test_falls_back_to_check_interrupts_tool_call_id(self, service):
        """When request has no tool_call_id, falls back to check_interrupts."""
        mock_agent = AsyncMock()
        mock_agent.aupdate_state = AsyncMock()
        mock_agent.ainvoke = AsyncMock()

        with patch.object(service, "check_interrupts", new_callable=AsyncMock) as mock_check, \
             patch("services.chat_metadata_service.chat_metadata_service") as mock_meta_svc:
            mock_check.return_value = {
                "type": "tool_approval_request",
                "tool_name": "send_email",
                "tool_call_id": "call_from_state",
            }
            mock_meta_svc.record_approval = AsyncMock()

            result = await service.resume_interrupt(
                "test-thread",
                {"type": "approve"},
                mock_agent,
            )

        assert result["success"] is True
        mock_meta_svc.record_approval.assert_awaited_once_with("test-thread", "call_from_state")

    @pytest.mark.asyncio
    async def test_skips_recording_when_no_tool_call_id_from_any_source(self, service):
        """No recording when neither request nor check_interrupts has tool_call_id."""
        mock_agent = AsyncMock()
        mock_agent.aupdate_state = AsyncMock()
        mock_agent.ainvoke = AsyncMock()

        with patch.object(service, "check_interrupts", new_callable=AsyncMock) as mock_check, \
             patch("services.chat_metadata_service.chat_metadata_service") as mock_meta_svc:
            mock_check.return_value = {
                "type": "tool_approval_request",
                "tool_name": "send_email",
                "tool_call_id": None,
            }
            mock_meta_svc.record_approval = AsyncMock()

            await service.resume_interrupt(
                "test-thread", {"type": "approve"}, mock_agent
            )

        mock_meta_svc.record_approval.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_recording_on_deny(self, service):
        """Denying a tool does not record an approval."""
        mock_agent = AsyncMock()
        mock_agent.aupdate_state = AsyncMock()
        mock_agent.ainvoke = AsyncMock()

        with patch("services.chat_metadata_service.chat_metadata_service") as mock_meta_svc:
            mock_meta_svc.record_approval = AsyncMock()

            await service.resume_interrupt(
                "test-thread", {"type": "deny"}, mock_agent
            )

        mock_meta_svc.record_approval.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_continues_on_metadata_failure(self, service):
        """Metadata recording failure doesn't block the resume."""
        mock_agent = AsyncMock()
        mock_agent.aupdate_state = AsyncMock()
        mock_agent.ainvoke = AsyncMock()

        with patch("services.chat_metadata_service.chat_metadata_service") as mock_meta_svc:
            mock_meta_svc.record_approval = AsyncMock(side_effect=Exception("DB down"))

            result = await service.resume_interrupt(
                "test-thread",
                {"type": "approve", "tool_call_id": "call_abc"},
                mock_agent,
            )

        assert result["success"] is True


class TestStreamChatApprovalPersistence:
    """Test that stream_chat() persists tool approvals when resuming from interrupt.

    Verifies that when approval flows through /chat/stream (Path B), stream_chat()
    calls chat_metadata_service.record_approval() so the "Approved" badge survives
    page reloads. Covers approve, always_allow, and deny scenarios.
    """

    def _make_interrupt_state(
        self,
        tool_name="ms_graph-send_email",
        tool_call_id="call_tool_abc123",
        tool_args=None,
    ):
        """Build mock agent state with a tool_approval_request interrupt.

        Matches real-world behaviour: tool_approval_helper puts tool_name/tool_args
        in the interrupt value, but NOT tool_call_id. The tool_call_id lives on the
        AIMessage.tool_calls in the state messages and must be resolved from there.
        """
        if tool_args is None:
            tool_args = {"recipients": ["user@example.com"], "subject": "Hello"}

        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "type": "tool_approval_request",
            "tool_name": tool_name,
            "tool_args": tool_args,
            # Note: no tool_call_id here — matches real tool_approval_helper.py
        }

        # The AIMessage in state.values.messages carries the tool_call_id
        # Args on the tool call match the interrupt tool_args for proper disambiguation
        ai_msg_with_tool_call = MagicMock()
        ai_msg_with_tool_call.tool_calls = [
            {"name": tool_name, "id": tool_call_id, "args": tool_args}
        ]

        state = MagicMock()
        state.interrupts = [mock_interrupt]
        state.values = {"messages": [ai_msg_with_tool_call]}
        return state

    def _make_mock_agent(self, state_with_interrupt):
        """Build a mock chat agent that returns interrupt state then clean state."""
        mock_state_no_interrupt = MagicMock()
        mock_state_no_interrupt.interrupts = []

        mock_agent = AsyncMock()
        mock_agent.aget_state = AsyncMock(
            side_effect=[state_with_interrupt, mock_state_no_interrupt]
        )

        ai_response = AIMessage(content="Email sent successfully.")

        async def mock_astream(*args, **kwargs):
            yield {"agent": {"messages": [ai_response]}}

        mock_agent.astream = mock_astream
        return mock_agent

    def _make_mock_checkpointer(self):
        """Build a mock checkpointer that indicates an existing conversation."""
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = {
            "channel_values": {
                "messages": [HumanMessage(content="Send an email to user@example.com")]
            }
        }
        return mock_checkpointer

    async def _run_stream(self, service, thread_id, user_response, mock_agent, mock_checkpointer):
        """Run stream_chat to completion and return collected events."""
        chat_request = ChatRequest(
            messages=[ChatMessage(role="user", content=user_response)],
            thread_id=thread_id,
        )
        mock_command_cls = MagicMock()
        mock_command_cls.return_value = MagicMock()

        with patch.dict("sys.modules", {"langgraph.types": MagicMock(Command=mock_command_cls)}), \
             patch("services.chat_metadata_service.chat_metadata_service") as mock_meta_svc:
            mock_meta_svc.record_approval = AsyncMock()

            events = []
            async for event in service.stream_chat(chat_request, mock_checkpointer, mock_agent):
                events.append(event)

            return events, mock_meta_svc

    @pytest.mark.asyncio
    async def test_stream_chat_records_approval_on_interrupt_resume(self, service):
        """stream_chat must call record_approval when resuming a tool approval interrupt.

        Uses real-world mock: tool_call_id is NOT in the interrupt value dict —
        it must be resolved from the AIMessage.tool_calls in state messages.
        """
        thread_id = "test-thread-approval"
        state = self._make_interrupt_state()
        agent = self._make_mock_agent(state)
        checkpointer = self._make_mock_checkpointer()

        events, mock_meta_svc = await self._run_stream(
            service, thread_id, "approve", agent, checkpointer
        )

        event_types = [e["type"] for e in events]
        assert "start" in event_types
        assert "complete" in event_types

        mock_meta_svc.record_approval.assert_awaited_once_with(
            thread_id, "call_tool_abc123"
        )

    @pytest.mark.asyncio
    async def test_stream_chat_records_approval_on_always_allow(self, service):
        """always_allow should also persist the approval."""
        thread_id = "test-thread-always-allow"
        state = self._make_interrupt_state()
        agent = self._make_mock_agent(state)
        checkpointer = self._make_mock_checkpointer()

        events, mock_meta_svc = await self._run_stream(
            service, thread_id, "always_allow", agent, checkpointer
        )

        mock_meta_svc.record_approval.assert_awaited_once_with(
            thread_id, "call_tool_abc123"
        )

    @pytest.mark.asyncio
    async def test_stream_chat_does_not_record_approval_on_deny(self, service):
        """deny should NOT persist an approval."""
        thread_id = "test-thread-deny"
        state = self._make_interrupt_state()
        agent = self._make_mock_agent(state)
        checkpointer = self._make_mock_checkpointer()

        events, mock_meta_svc = await self._run_stream(
            service, thread_id, "deny", agent, checkpointer
        )

        mock_meta_svc.record_approval.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stream_chat_disambiguates_tool_call_by_args(self, service):
        """When the same tool is called multiple times, match by args to find the correct one.

        Simulates: two ms_graph-send_email calls in message history with different args.
        The interrupt's tool_args should match the second (most recent) call, not the first.
        """
        tool_name = "ms_graph-send_email"
        first_args = {"recipients": ["alice@example.com"], "subject": "First"}
        second_args = {"recipients": ["bob@example.com"], "subject": "Second"}

        # Build state with two tool calls of the same name but different args
        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "type": "tool_approval_request",
            "tool_name": tool_name,
            "tool_args": second_args,
        }

        ai_msg = MagicMock()
        ai_msg.tool_calls = [
            {"name": tool_name, "id": "call_first", "args": first_args},
            {"name": tool_name, "id": "call_second", "args": second_args},
        ]

        state = MagicMock()
        state.interrupts = [mock_interrupt]
        state.values = {"messages": [ai_msg]}

        agent = self._make_mock_agent(state)
        checkpointer = self._make_mock_checkpointer()

        events, mock_meta_svc = await self._run_stream(
            service, "test-thread-disambig", "approve", agent, checkpointer
        )

        # Must resolve to "call_second" (matching args), NOT "call_first"
        mock_meta_svc.record_approval.assert_awaited_once_with(
            "test-thread-disambig", "call_second"
        )

    @pytest.mark.asyncio
    async def test_stream_chat_falls_back_to_name_only_when_args_differ(self, service):
        """When tool_args don't exactly match any tool call, fall back to name-only match.

        This ensures backward compatibility when args are slightly different
        (e.g., serialization differences).
        """
        tool_name = "ms_graph-send_email"
        interrupt_args = {"recipients": ["user@example.com"], "subject": "Hello"}
        # Tool call args differ slightly (extra field)
        tool_call_args = {"recipients": ["user@example.com"], "subject": "Hello", "body": "Hi"}

        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "type": "tool_approval_request",
            "tool_name": tool_name,
            "tool_args": interrupt_args,
        }

        ai_msg = MagicMock()
        ai_msg.tool_calls = [
            {"name": tool_name, "id": "call_fallback", "args": tool_call_args},
        ]

        state = MagicMock()
        state.interrupts = [mock_interrupt]
        state.values = {"messages": [ai_msg]}

        agent = self._make_mock_agent(state)
        checkpointer = self._make_mock_checkpointer()

        events, mock_meta_svc = await self._run_stream(
            service, "test-thread-fallback", "approve", agent, checkpointer
        )

        # Falls back to name-only match
        mock_meta_svc.record_approval.assert_awaited_once_with(
            "test-thread-fallback", "call_fallback"
        )


class TestGlobalInstance:
    """Test the global chat_service instance."""

    def test_global_instance_exists(self):
        """Test that the global chat_service instance is available."""
        assert chat_service is not None
        assert isinstance(chat_service, ChatService)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

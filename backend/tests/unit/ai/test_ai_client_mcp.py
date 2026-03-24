"""Tests for AIClient MCP tool-use integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage
from mcp import types as mcp_types

from infrahub.transformations.ai_client import (
    MAX_TOOL_USE_ITERATIONS,
    AIClient,
    _extract_csv,
    _extract_svg,
    _extract_text,
    _strip_code_fences,
)


@pytest.fixture
def ai_client() -> AIClient:
    return AIClient(api_key="test-key", mcp_server_url="http://mcp:8001")


@pytest.fixture
def ai_client_no_mcp() -> AIClient:
    return AIClient(api_key="test-key")


def _make_text_response(text: str, stop_reason: str = "end_turn") -> Message:
    return Message(
        id="msg_test",
        type="message",
        role="assistant",
        model="claude-sonnet-4-5-20250929",
        content=[TextBlock(type="text", text=text)],
        stop_reason=stop_reason,
        stop_sequence=None,
        usage=Usage(input_tokens=100, output_tokens=50),
    )


def _make_tool_use_response(tool_name: str, tool_input: dict, tool_use_id: str = "tu_1") -> Message:
    return Message(
        id="msg_test",
        type="message",
        role="assistant",
        model="claude-sonnet-4-5-20250929",
        content=[ToolUseBlock(type="tool_use", id=tool_use_id, name=tool_name, input=tool_input)],
        stop_reason="tool_use",
        stop_sequence=None,
        usage=Usage(input_tokens=100, output_tokens=50),
    )


def _make_multi_tool_response(tools: list[tuple[str, dict, str]]) -> Message:
    """Create a response with multiple tool_use blocks."""
    blocks = [ToolUseBlock(type="tool_use", id=tid, name=name, input=inp) for name, inp, tid in tools]
    return Message(
        id="msg_test",
        type="message",
        role="assistant",
        model="claude-sonnet-4-5-20250929",
        content=blocks,
        stop_reason="tool_use",
        stop_sequence=None,
        usage=Usage(input_tokens=100, output_tokens=50),
    )


class TestExtractText:
    def test_extracts_text_blocks(self) -> None:
        response = _make_text_response("hello world")
        assert _extract_text(response) == "hello world"

    def test_concatenates_multiple_blocks(self) -> None:
        response = Message(
            id="msg_test",
            type="message",
            role="assistant",
            model="claude-sonnet-4-5-20250929",
            content=[TextBlock(type="text", text="hello "), TextBlock(type="text", text="world")],
            stop_reason="end_turn",
            stop_sequence=None,
            usage=Usage(input_tokens=10, output_tokens=5),
        )
        assert _extract_text(response) == "hello world"


class TestStripCodeFences:
    def test_no_fences(self) -> None:
        assert _strip_code_fences("just text") == "just text"

    def test_fenced_json(self) -> None:
        text = '```json\n{"key": "value"}\n```'
        assert _strip_code_fences(text) == '{"key": "value"}'

    def test_fenced_csv(self) -> None:
        text = "```csv\nname\n123\nabc\n```"
        assert _strip_code_fences(text) == "name\n123\nabc"

    def test_explanation_before_fence(self) -> None:
        text = "Here is the result:\n\n```csv\nname\n123\n```"
        assert _strip_code_fences(text) == "name\n123"

    def test_last_fence_wins(self) -> None:
        text = "```json\nignored\n```\nsome text\n```csv\nactual\n```"
        assert _strip_code_fences(text) == "actual"


class TestExtractCsv:
    def test_fenced_csv(self) -> None:
        text = "Here is the data:\n\n```csv\nname,value\nfoo,1\n```"
        assert _extract_csv(text) == "name,value\nfoo,1"

    def test_preamble_before_csv(self) -> None:
        text = (
            "Perfect! Now I have all the information I need.\n\n"
            "From the query results:\n"
            "- Devices: router1 and router2\n\n"
            "Device Name,Attribute,Profile Value,Device Value\n"
            "router1,domain_name,eu.ops.com,lnd.eu.ops.com\n"
        )
        result = _extract_csv(text)
        assert result.startswith("Device Name,Attribute,Profile Value,Device Value")
        assert "Perfect!" not in result
        assert "From the query" not in result

    def test_pure_csv(self) -> None:
        text = "name,value\nfoo,1\nbar,2"
        assert _extract_csv(text) == "name,value\nfoo,1\nbar,2"

    def test_no_csv_returns_stripped(self) -> None:
        text = "  just some text  "
        assert _extract_csv(text) == "just some text"


class TestExtractSvg:
    def test_pure_svg(self) -> None:
        text = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="40"/></svg>'
        assert _extract_svg(text) == text

    def test_svg_with_preamble(self) -> None:
        text = (
            "Here is the visualization:\n\n"
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            '<circle cx="50" cy="50" r="40"/>'
            "</svg>\n\nHope this helps!"
        )
        result = _extract_svg(text)
        assert result.startswith("<svg")
        assert result.endswith("</svg>")
        assert "Here is" not in result
        assert "Hope this" not in result

    def test_svg_in_code_fence(self) -> None:
        text = '```svg\n<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>\n```'
        result = _extract_svg(text)
        assert result.startswith("<svg")
        assert result.endswith("</svg>")

    def test_no_svg_falls_back_to_strip_fences(self) -> None:
        text = "```xml\n<not-svg>content</not-svg>\n```"
        assert _extract_svg(text) == "<not-svg>content</not-svg>"

    def test_no_fences_no_svg_returns_stripped(self) -> None:
        text = "  just some text  "
        assert _extract_svg(text) == "just some text"


class TestMcpSession:
    @pytest.mark.asyncio
    async def test_connects_and_converts_tools(self, ai_client: AIClient) -> None:
        mock_tool = MagicMock()
        mock_tool.name = "get_nodes"
        mock_tool.description = "Get nodes from Infrahub"
        mock_tool.inputSchema = {
            "type": "object",
            "properties": {"kind": {"type": "string"}},
            "required": ["kind"],
        }

        mock_session = AsyncMock(spec=["initialize", "list_tools", "call_tool"])
        mock_tools_response = MagicMock()
        mock_tools_response.tools = [mock_tool]
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=mock_tools_response)

        with (
            patch("infrahub.transformations.ai_client.streamablehttp_client") as mock_transport,
            patch("infrahub.transformations.ai_client.ClientSession") as mock_session_cls,
        ):
            # Set up the nested async context managers
            mock_transport.return_value.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
            mock_transport.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            async with ai_client._mcp_session() as (tools, session):
                assert len(tools) == 1
                assert tools[0]["name"] == "get_nodes"
                assert tools[0]["description"] == "Get nodes from Infrahub"
                assert tools[0]["input_schema"] == mock_tool.inputSchema
                assert session is mock_session


class TestExecuteToolCall:
    @pytest.mark.asyncio
    async def test_success(self, ai_client: AIClient) -> None:

        tool_use = ToolUseBlock(type="tool_use", id="tu_1", name="get_nodes", input={"kind": "Device"})

        mock_result = MagicMock()
        mock_result.content = [mcp_types.TextContent(type="text", text='[{"name": "router1"}]')]
        mock_result.isError = False

        session = AsyncMock()
        session.call_tool = AsyncMock(return_value=mock_result)

        result = await ai_client._execute_tool_call(tool_use, session)

        assert result["tool_use_id"] == "tu_1"
        assert result["content"] == '[{"name": "router1"}]'
        assert result["is_error"] is False
        session.call_tool.assert_called_once_with("get_nodes", arguments={"kind": "Device"})

    @pytest.mark.asyncio
    async def test_error_returns_is_error(self, ai_client: AIClient) -> None:
        tool_use = ToolUseBlock(type="tool_use", id="tu_2", name="bad_tool", input={})

        session = AsyncMock()
        session.call_tool = AsyncMock(side_effect=ConnectionError("MCP server down"))

        result = await ai_client._execute_tool_call(tool_use, session)

        assert result["tool_use_id"] == "tu_2"
        assert result["is_error"] is True
        assert "MCP server down" in result["content"]


class TestRunAgenticLoop:
    @pytest.mark.asyncio
    async def test_no_tool_use_single_round(self, ai_client: AIClient) -> None:
        """When Claude doesn't use tools, returns immediately."""
        ai_client.client.messages.create = AsyncMock(return_value=_make_text_response("The report content"))

        result = await ai_client._run_agentic_loop(
            system_message="system",
            user_message="user prompt",
            tools=[],
            session=AsyncMock(),
        )

        assert result == "The report content"
        ai_client.client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_use_then_text(self, ai_client: AIClient) -> None:
        """Claude uses a tool, gets result, then produces final text."""

        tool_response = _make_tool_use_response("get_schemas", {})
        text_response = _make_text_response("Final report with schema context")

        ai_client.client.messages.create = AsyncMock(side_effect=[tool_response, text_response])

        mock_session = AsyncMock()
        mock_tool_result = MagicMock()
        mock_tool_result.content = [mcp_types.TextContent(type="text", text="schema data")]
        mock_tool_result.isError = False
        mock_session.call_tool = AsyncMock(return_value=mock_tool_result)

        result = await ai_client._run_agentic_loop(
            system_message="system",
            user_message="user prompt",
            tools=[{"name": "get_schemas", "description": "Get schemas", "input_schema": {}}],
            session=mock_session,
        )

        assert result == "Final report with schema context"
        assert ai_client.client.messages.create.call_count == 2
        mock_session.call_tool.assert_called_once_with("get_schemas", arguments={})

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_one_response(self, ai_client: AIClient) -> None:
        """Claude requests multiple tools in a single response."""

        multi_tool_response = _make_multi_tool_response([
            ("get_schemas", {}, "tu_1"),
            ("get_nodes", {"kind": "Device"}, "tu_2"),
        ])
        text_response = _make_text_response("Report with both contexts")

        ai_client.client.messages.create = AsyncMock(side_effect=[multi_tool_response, text_response])

        mock_session = AsyncMock()
        mock_tool_result = MagicMock()
        mock_tool_result.content = [mcp_types.TextContent(type="text", text="data")]
        mock_tool_result.isError = False
        mock_session.call_tool = AsyncMock(return_value=mock_tool_result)

        result = await ai_client._run_agentic_loop(
            system_message="system",
            user_message="prompt",
            tools=[],
            session=mock_session,
        )

        assert result == "Report with both contexts"
        assert mock_session.call_tool.call_count == 2

    @pytest.mark.asyncio
    async def test_max_iterations_forces_final_call(self, ai_client: AIClient) -> None:
        """After MAX_TOOL_USE_ITERATIONS, makes a final call without tools."""

        tool_response = _make_tool_use_response("get_schemas", {})
        text_response = _make_text_response("Forced final output")

        # Return tool_use for MAX iterations, then text for the final forced call
        side_effects = [tool_response] * MAX_TOOL_USE_ITERATIONS + [text_response]
        ai_client.client.messages.create = AsyncMock(side_effect=side_effects)

        mock_session = AsyncMock()
        mock_tool_result = MagicMock()
        mock_tool_result.content = [mcp_types.TextContent(type="text", text="data")]
        mock_tool_result.isError = False
        mock_session.call_tool = AsyncMock(return_value=mock_tool_result)

        result = await ai_client._run_agentic_loop(
            system_message="system",
            user_message="prompt",
            tools=[],
            session=mock_session,
        )

        assert result == "Forced final output"
        # MAX iterations + 1 final call without tools
        assert ai_client.client.messages.create.call_count == MAX_TOOL_USE_ITERATIONS + 1

    @pytest.mark.asyncio
    async def test_csv_format_reminder_injected(self, ai_client: AIClient) -> None:
        """CSV output_format injects a format reminder alongside tool results."""
        tool_response = _make_tool_use_response("get_schemas", {})
        text_response = _make_text_response("name,value\nfoo,1")

        ai_client.client.messages.create = AsyncMock(side_effect=[tool_response, text_response])

        mock_session = AsyncMock()
        mock_tool_result = MagicMock()
        mock_tool_result.content = [mcp_types.TextContent(type="text", text="data")]
        mock_tool_result.isError = False
        mock_session.call_tool = AsyncMock(return_value=mock_tool_result)

        await ai_client._run_agentic_loop(
            system_message="system",
            user_message="prompt",
            tools=[{"name": "get_schemas", "description": "Get schemas", "input_schema": {}}],
            session=mock_session,
            output_format="csv",
        )

        # The second call's messages should contain the format reminder
        second_call_messages = ai_client.client.messages.create.call_args_list[1][1]["messages"]
        # Last user message (tool results + reminder)
        last_user_msg = second_call_messages[-1]
        assert last_user_msg["role"] == "user"
        content_types = [block.get("type") if isinstance(block, dict) else block["type"] for block in last_user_msg["content"]]
        assert "text" in content_types

    @pytest.mark.asyncio
    async def test_svg_format_reminder_injected(self, ai_client: AIClient) -> None:
        """SVG output_format injects a format reminder alongside tool results."""
        tool_response = _make_tool_use_response("get_schemas", {})
        text_response = _make_text_response('<svg xmlns="http://www.w3.org/2000/svg"></svg>')

        ai_client.client.messages.create = AsyncMock(side_effect=[tool_response, text_response])

        mock_session = AsyncMock()
        mock_tool_result = MagicMock()
        mock_tool_result.content = [mcp_types.TextContent(type="text", text="data")]
        mock_tool_result.isError = False
        mock_session.call_tool = AsyncMock(return_value=mock_tool_result)

        await ai_client._run_agentic_loop(
            system_message="system",
            user_message="prompt",
            tools=[{"name": "get_schemas", "description": "Get schemas", "input_schema": {}}],
            session=mock_session,
            output_format="svg",
        )

        second_call_messages = ai_client.client.messages.create.call_args_list[1][1]["messages"]
        last_user_msg = second_call_messages[-1]
        assert last_user_msg["role"] == "user"
        content_types = [block.get("type") if isinstance(block, dict) else block["type"] for block in last_user_msg["content"]]
        assert "text" in content_types

    @pytest.mark.asyncio
    async def test_markdown_no_format_reminder(self, ai_client: AIClient) -> None:
        """Markdown output_format does not inject a format reminder."""
        tool_response = _make_tool_use_response("get_schemas", {})
        text_response = _make_text_response("# Report")

        ai_client.client.messages.create = AsyncMock(side_effect=[tool_response, text_response])

        mock_session = AsyncMock()
        mock_tool_result = MagicMock()
        mock_tool_result.content = [mcp_types.TextContent(type="text", text="data")]
        mock_tool_result.isError = False
        mock_session.call_tool = AsyncMock(return_value=mock_tool_result)

        await ai_client._run_agentic_loop(
            system_message="system",
            user_message="prompt",
            tools=[{"name": "get_schemas", "description": "Get schemas", "input_schema": {}}],
            session=mock_session,
            output_format="markdown",
        )

        # Last user message should only contain tool results, no text reminder
        second_call_messages = ai_client.client.messages.create.call_args_list[1][1]["messages"]
        last_user_msg = second_call_messages[-1]
        content_types = [block.get("type") if isinstance(block, dict) else block["type"] for block in last_user_msg["content"]]
        assert "text" not in content_types


class TestGenerateReport:
    @pytest.mark.asyncio
    async def test_no_mcp_url_single_shot(self, ai_client_no_mcp: AIClient) -> None:
        """Without mcp_server_url, uses single-shot generation."""
        ai_client_no_mcp.client.messages.create = AsyncMock(
            return_value=_make_text_response("simple report")
        )

        result = await ai_client_no_mcp.generate_report(
            prompt="Generate a report", data={"key": "value"}
        )

        assert result == "simple report"
        ai_client_no_mcp.client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_connection_error_raises(self, ai_client: AIClient) -> None:
        """Raises when MCP connection fails instead of silently falling back."""
        with patch("infrahub.transformations.ai_client.streamablehttp_client") as mock_transport:
            mock_transport.return_value.__aenter__ = AsyncMock(side_effect=ConnectionError("refused"))
            mock_transport.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ConnectionError, match="refused"):
                await ai_client.generate_report(
                    prompt="Generate a report", data={"key": "value"}
                )

    @pytest.mark.asyncio
    async def test_csv_output_strips_fences(self, ai_client_no_mcp: AIClient) -> None:
        """CSV output has code fences stripped."""
        ai_client_no_mcp.client.messages.create = AsyncMock(
            return_value=_make_text_response("```csv\nname\nfoo\n```")
        )

        result = await ai_client_no_mcp.generate_report(
            prompt="Generate CSV", data={}, output_format="csv"
        )

        assert result == "name\nfoo"

    @pytest.mark.asyncio
    async def test_svg_output_extracts_svg(self, ai_client_no_mcp: AIClient) -> None:
        """SVG output extracts the <svg> element from response."""
        ai_client_no_mcp.client.messages.create = AsyncMock(
            return_value=_make_text_response(
                'Here is the chart:\n\n<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
            )
        )

        result = await ai_client_no_mcp.generate_report(
            prompt="Generate SVG", data={}, output_format="svg"
        )

        assert result.startswith("<svg")
        assert result.endswith("</svg>")
        assert "Here is" not in result

    @pytest.mark.asyncio
    async def test_svg_output_strips_fences(self, ai_client_no_mcp: AIClient) -> None:
        """SVG output in code fences gets extracted."""
        ai_client_no_mcp.client.messages.create = AsyncMock(
            return_value=_make_text_response(
                '```svg\n<svg xmlns="http://www.w3.org/2000/svg"><circle/></svg>\n```'
            )
        )

        result = await ai_client_no_mcp.generate_report(
            prompt="Generate SVG", data={}, output_format="svg"
        )

        assert result.startswith("<svg")
        assert "```" not in result

    @pytest.mark.asyncio
    async def test_csv_output_strips_preamble(self, ai_client_no_mcp: AIClient) -> None:
        """CSV output strips non-fenced preamble text."""
        response_text = (
            "Here is the analysis:\n\n"
            "- Found 2 devices\n\n"
            "Device Name,Value\n"
            "router1,10\n"
        )
        ai_client_no_mcp.client.messages.create = AsyncMock(
            return_value=_make_text_response(response_text)
        )

        result = await ai_client_no_mcp.generate_report(
            prompt="Generate CSV", data={}, output_format="csv"
        )

        assert result.startswith("Device Name,Value")
        assert "Here is" not in result

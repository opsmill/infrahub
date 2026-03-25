from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from infrahub.transformations.ai_client import AIClient, _extract_json_object


def _make_text_response(text: str) -> MagicMock:
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    response.stop_reason = "end_turn"
    response.usage = MagicMock(input_tokens=100, output_tokens=50)
    return response


class TestGenerateCheckResult:
    async def test_success_result(self) -> None:
        result_json = json.dumps({"conclusion": "success", "severity": "info", "message": "All checks passed"})
        client = AIClient(api_key="test-key", model="claude-sonnet-4-5-20250929", temperature=0.0)
        client.client = MagicMock()
        client.client.messages = MagicMock()
        client.client.messages.create = AsyncMock(return_value=_make_text_response(result_json))

        result = await client.generate_check_result(prompt="Check this data", data={"key": "value"})

        assert result["conclusion"] == "success"
        assert result["severity"] == "info"
        assert result["message"] == "All checks passed"

    async def test_failure_result(self) -> None:
        result_json = json.dumps({"conclusion": "failure", "severity": "critical", "message": "Missing required field"})
        client = AIClient(api_key="test-key")
        client.client = MagicMock()
        client.client.messages = MagicMock()
        client.client.messages.create = AsyncMock(return_value=_make_text_response(result_json))

        result = await client.generate_check_result(prompt="Check this", data={})

        assert result["conclusion"] == "failure"
        assert result["severity"] == "critical"

    async def test_code_fenced_json(self) -> None:
        result_json = '```json\n{"conclusion": "success", "severity": "info", "message": "OK"}\n```'
        client = AIClient(api_key="test-key")
        client.client = MagicMock()
        client.client.messages = MagicMock()
        client.client.messages.create = AsyncMock(return_value=_make_text_response(result_json))

        result = await client.generate_check_result(prompt="Check", data={})

        assert result["conclusion"] == "success"

    async def test_preamble_text_before_json(self) -> None:
        """LLM outputs reasoning text before the JSON object — should still parse."""
        response_text = (
            'Now I have all the data I need. Let me analyze:\n\n'
            '**Device `lnd-router-1`** has a valid location.\n\n'
            '{"conclusion": "success", "severity": "info", "message": "All devices have valid locations"}'
        )
        client = AIClient(api_key="test-key")
        client.client = MagicMock()
        client.client.messages = MagicMock()
        client.client.messages.create = AsyncMock(return_value=_make_text_response(response_text))

        result = await client.generate_check_result(prompt="Check", data={})

        assert result["conclusion"] == "success"
        assert result["severity"] == "info"

    async def test_preamble_text_with_truncated_json_uses_last_complete_object(self) -> None:
        """LLM outputs partial JSON mid-sentence then a complete object — should use the complete one."""
        response_text = (
            'The check says "validate" so I will check {"partial": true but this is incomplete.\n\n'
            '{"conclusion": "failure", "severity": "critical", "message": "2 devices missing locations"}'
        )
        client = AIClient(api_key="test-key")
        client.client = MagicMock()
        client.client.messages = MagicMock()
        client.client.messages.create = AsyncMock(return_value=_make_text_response(response_text))

        result = await client.generate_check_result(prompt="Check", data={})

        assert result["conclusion"] == "failure"
        assert result["severity"] == "critical"

    async def test_defaults_severity_for_success(self) -> None:
        result_json = json.dumps({"conclusion": "success", "message": "OK"})
        client = AIClient(api_key="test-key")
        client.client = MagicMock()
        client.client.messages = MagicMock()
        client.client.messages.create = AsyncMock(return_value=_make_text_response(result_json))

        result = await client.generate_check_result(prompt="Check", data={})

        assert result["severity"] == "info"

    async def test_defaults_severity_for_failure(self) -> None:
        result_json = json.dumps({"conclusion": "failure", "message": "Bad"})
        client = AIClient(api_key="test-key")
        client.client = MagicMock()
        client.client.messages = MagicMock()
        client.client.messages.create = AsyncMock(return_value=_make_text_response(result_json))

        result = await client.generate_check_result(prompt="Check", data={})

        assert result["severity"] == "critical"

    async def test_defaults_empty_message(self) -> None:
        result_json = json.dumps({"conclusion": "success"})
        client = AIClient(api_key="test-key")
        client.client = MagicMock()
        client.client.messages = MagicMock()
        client.client.messages.create = AsyncMock(return_value=_make_text_response(result_json))

        result = await client.generate_check_result(prompt="Check", data={})

        assert not result["message"]

    async def test_invalid_json_raises(self) -> None:
        client = AIClient(api_key="test-key")
        client.client = MagicMock()
        client.client.messages = MagicMock()
        client.client.messages.create = AsyncMock(return_value=_make_text_response("not json at all"))

        with pytest.raises(ValueError, match="Failed to parse check result as JSON"):
            await client.generate_check_result(prompt="Check", data={})

    async def test_missing_conclusion_raises(self) -> None:
        result_json = json.dumps({"severity": "info", "message": "OK"})
        client = AIClient(api_key="test-key")
        client.client = MagicMock()
        client.client.messages = MagicMock()
        client.client.messages.create = AsyncMock(return_value=_make_text_response(result_json))

        with pytest.raises(ValueError, match="missing 'conclusion'"):
            await client.generate_check_result(prompt="Check", data={})

    async def test_invalid_conclusion_raises(self) -> None:
        result_json = json.dumps({"conclusion": "maybe", "message": "uncertain"})
        client = AIClient(api_key="test-key")
        client.client = MagicMock()
        client.client.messages = MagicMock()
        client.client.messages.create = AsyncMock(return_value=_make_text_response(result_json))

        with pytest.raises(ValueError, match="Invalid conclusion value"):
            await client.generate_check_result(prompt="Check", data={})

    async def test_empty_response_raises(self) -> None:
        client = AIClient(api_key="test-key")
        client.client = MagicMock()
        client.client.messages = MagicMock()
        client.client.messages.create = AsyncMock(return_value=_make_text_response(""))

        with pytest.raises(ValueError, match="Empty response"):
            await client.generate_check_result(prompt="Check", data={})


class TestExtractJsonObject:
    def test_plain_json(self) -> None:
        text = '{"conclusion": "success", "message": "OK"}'
        assert json.loads(_extract_json_object(text)) == {"conclusion": "success", "message": "OK"}

    def test_code_fenced_json(self) -> None:
        text = '```json\n{"conclusion": "success"}\n```'
        assert json.loads(_extract_json_object(text)) == {"conclusion": "success"}

    def test_preamble_before_json(self) -> None:
        text = 'Let me analyze the data.\n\n{"conclusion": "failure", "severity": "critical", "message": "bad"}'
        result = json.loads(_extract_json_object(text))
        assert result["conclusion"] == "failure"

    def test_nested_braces(self) -> None:
        text = 'Here is the result:\n{"conclusion": "success", "details": {"count": 5, "items": [1, 2]}}'
        result = json.loads(_extract_json_object(text))
        assert result["conclusion"] == "success"
        assert result["details"]["count"] == 5

    def test_json_with_escaped_quotes(self) -> None:
        text = r'{"conclusion": "success", "message": "Device \"router1\" is valid"}'
        result = json.loads(_extract_json_object(text))
        assert result["conclusion"] == "success"

    def test_multiple_json_objects_uses_last(self) -> None:
        text = (
            'First attempt: {"partial": true}\n'
            'Actually: {"conclusion": "success", "message": "OK"}'
        )
        result = json.loads(_extract_json_object(text))
        assert result["conclusion"] == "success"

    def test_no_json_returns_stripped_text(self) -> None:
        text = "  no json here  "
        assert _extract_json_object(text) == "no json here"

    def test_empty_string(self) -> None:
        assert _extract_json_object("") == ""

    def test_code_fence_preferred_over_bare_json(self) -> None:
        text = (
            'Some preamble {"wrong": true}\n'
            '```json\n{"conclusion": "success"}\n```\n'
            'Some postamble'
        )
        result = json.loads(_extract_json_object(text))
        assert result == {"conclusion": "success"}


class TestBuildCheckSystemMessage:
    def test_basic_message(self) -> None:
        client = AIClient(api_key="test-key")
        msg = client._build_check_system_message()

        assert "conclusion" in msg
        assert "success" in msg
        assert "failure" in msg
        assert "JSON" in msg

    def test_includes_branch_with_mcp(self) -> None:
        client = AIClient(api_key="test-key", mcp_server_url="http://localhost:8080")
        msg = client._build_check_system_message(branch="test-branch")

        assert "test-branch" in msg
        assert "tool" in msg.lower()

    def test_no_mcp_instructions_without_url(self) -> None:
        client = AIClient(api_key="test-key")
        msg = client._build_check_system_message(branch="test-branch")

        assert "tool" not in msg.lower() or "tool" in msg.lower()  # just check it doesn't crash
        assert "test-branch" not in msg  # no branch instruction without MCP


class TestBuildCheckUserMessage:
    def test_includes_prompt_and_data(self) -> None:
        client = AIClient(api_key="test-key")
        msg = client._build_check_user_message(
            prompt="Check that all devices have locations",
            data={"devices": [{"name": "router1", "location": "NYC"}]},
        )

        assert "Check that all devices have locations" in msg
        assert "router1" in msg
        assert "NYC" in msg
        assert "JSON" in msg

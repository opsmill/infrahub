"""Unit tests for infrahub.ai.claude module."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infrahub.ai.claude import ClaudeExtractionClient, _IMAGE_MIME_TYPES, _PDF_MIME_TYPES


def _make_client(model: str = "claude-sonnet-4-6") -> ClaudeExtractionClient:
    with patch("infrahub.ai.claude.anthropic.AsyncAnthropic"):
        client = ClaudeExtractionClient(api_key="test-key", model=model)
    return client


def _make_text_response(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


# ---------------------------------------------------------------------------
# _build_content_block
# ---------------------------------------------------------------------------


def test_build_content_block_pdf() -> None:
    client = _make_client()
    data = b"%PDF-1.4 ..."
    block = client._build_content_block(content=data, mime_type="application/pdf")

    assert block["type"] == "document"
    assert block["source"]["type"] == "base64"
    assert block["source"]["media_type"] == "application/pdf"
    assert block["source"]["data"] == base64.standard_b64encode(data).decode("ascii")


@pytest.mark.parametrize("mime_type", sorted(_IMAGE_MIME_TYPES))
def test_build_content_block_image(mime_type: str) -> None:
    client = _make_client()
    data = b"\x89PNG\r\n"
    block = client._build_content_block(content=data, mime_type=mime_type)

    assert block["type"] == "image"
    assert block["source"]["media_type"] == mime_type
    assert block["source"]["data"] == base64.standard_b64encode(data).decode("ascii")


def test_build_content_block_plain_text() -> None:
    client = _make_client()
    text_data = b"Hello, world!"
    block = client._build_content_block(content=text_data, mime_type="text/plain")

    assert block["type"] == "text"
    assert block["text"] == "Hello, world!"


def test_build_content_block_unknown_binary_falls_back_to_base64() -> None:
    client = _make_client()
    binary_data = bytes(range(256))
    block = client._build_content_block(content=binary_data, mime_type="application/octet-stream")

    assert block["type"] == "text"
    assert "base64" in block["text"].lower()


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_returns_text_response() -> None:
    with patch("infrahub.ai.claude.anthropic.AsyncAnthropic") as mock_anthropic_cls:
        mock_client_instance = MagicMock()
        mock_anthropic_cls.return_value = mock_client_instance

        expected_json = '{"title": "Test Contract"}'
        mock_client_instance.messages.create = AsyncMock(return_value=_make_text_response(expected_json))

        client = ClaudeExtractionClient(api_key="test-key")
        result = await client.extract(
            content=b"Contract text here",
            mime_type="text/plain",
            system_prompt="Extract the title.",
        )

    assert result == expected_json
    mock_client_instance.messages.create.assert_called_once()
    call_kwargs = mock_client_instance.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-6"
    assert call_kwargs["system"] == "Extract the title."


@pytest.mark.asyncio
async def test_extract_truncates_large_files() -> None:
    from infrahub.ai.claude import _MAX_FILE_BYTES

    oversized = b"x" * (_MAX_FILE_BYTES + 1024)

    with patch("infrahub.ai.claude.anthropic.AsyncAnthropic") as mock_anthropic_cls:
        mock_client_instance = MagicMock()
        mock_anthropic_cls.return_value = mock_client_instance
        mock_client_instance.messages.create = AsyncMock(return_value=_make_text_response("{}"))

        client = ClaudeExtractionClient(api_key="test-key")
        await client.extract(content=oversized, mime_type="text/plain", system_prompt="Extract.")

    # The content block sent to Claude should be truncated
    call_kwargs = mock_client_instance.messages.create.call_args.kwargs
    content_blocks = call_kwargs["messages"][0]["content"]
    text_block = next(
        b for b in content_blocks if b.get("type") == "text" and b.get("text") != "Extract the data as instructed."
    )
    assert len(text_block["text"].encode()) <= _MAX_FILE_BYTES

from __future__ import annotations

import base64
import logging
from typing import Any

import anthropic

log = logging.getLogger(__name__)

# MIME types that Claude's API supports as document blocks
_PDF_MIME_TYPES = frozenset({"application/pdf"})

# MIME types that Claude's API supports as image blocks
_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})

# MIME types treated as plain text (sent as text blocks)
_TEXT_MIME_PREFIXES = ("text/",)

# Maximum file size to send to Claude (5 MB)
_MAX_FILE_BYTES = 5 * 1024 * 1024


class ClaudeExtractionClient:
    """Thin wrapper around the Anthropic SDK for AI-powered data extraction from files."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def extract(
        self,
        content: bytes,
        mime_type: str,
        system_prompt: str,
    ) -> str:
        """Send file content to Claude with the given system prompt and return the text response.

        Args:
            content: Raw file content.
            mime_type: MIME type of the file (e.g. 'application/pdf', 'text/plain').
            system_prompt: Prompt describing what to extract and in what format.

        Returns:
            The text of Claude's first response block.
        """
        if len(content) > _MAX_FILE_BYTES:
            log.warning(
                "File exceeds maximum size of %d bytes (%d bytes); truncating",
                _MAX_FILE_BYTES,
                len(content),
            )
            content = content[:_MAX_FILE_BYTES]

        content_block = self._build_content_block(content=content, mime_type=mime_type)
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [content_block, {"type": "text", "text": "Extract the data as instructed."}],
                }
            ],
        )

        for block in message.content:
            if block.type == "text":
                return block.text

        return ""

    def _build_content_block(self, content: bytes, mime_type: str) -> dict[str, Any]:
        """Build the appropriate Anthropic API content block for the given MIME type."""
        if mime_type in _PDF_MIME_TYPES:
            return {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(content).decode("ascii"),
                },
            }

        if mime_type in _IMAGE_MIME_TYPES:
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": base64.standard_b64encode(content).decode("ascii"),
                },
            }

        # For text-based MIME types and any unknown binary format, decode to text
        if any(mime_type.startswith(prefix) for prefix in _TEXT_MIME_PREFIXES):
            text = content.decode("utf-8", errors="replace")
        else:
            # For unknown binary types, try UTF-8 decode; if it fails, use base64 text
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = f"[Binary file, base64-encoded]\n{base64.standard_b64encode(content).decode('ascii')}"

        return {"type": "text", "text": text}

"""AI client for Claude API integration with MCP support."""

from __future__ import annotations

import json
import os
from typing import Any

from anthropic import AsyncAnthropic
from structlog import get_logger

log = get_logger()


class AIClient:
    """Client for interacting with Claude API to generate reports."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-5-20250929",
        temperature: float = 1.0,
        max_tokens: int = 4096,
        mcp_server_url: str | None = None,
    ) -> None:
        """Initialize the AI client.

        Args:
            api_key: Anthropic API key. If not provided, will use ANTHROPIC_API_KEY env var.
            model: Claude model to use for generation.
            temperature: Temperature for Claude API (0.0-1.0).
            max_tokens: Maximum tokens for Claude API response.
            mcp_server_url: URL of the Infrahub MCP server (optional).
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable must be set or api_key must be provided")

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.mcp_server_url = mcp_server_url or os.getenv("INFRAHUB_MCP_SERVER_URL")

        self.client = AsyncAnthropic(api_key=self.api_key)

    async def generate_report(
        self,
        prompt: str,
        data: dict[str, Any],
        output_format: str = "markdown",
    ) -> str:
        """Generate a report using Claude API.

        Args:
            prompt: The prompt template (can include references to data).
            data: The input data from GraphQL query.
            output_format: Output format - "markdown" or "csv".

        Returns:
            Generated report content as string.

        Raises:
            ValueError: If output_format is not supported.
            Exception: If Claude API call fails.
        """
        if output_format not in ["markdown", "csv"]:
            raise ValueError(f"Unsupported output format: {output_format}. Must be 'markdown' or 'csv'.")

        # Prepare the system message with format instructions
        system_message = self._build_system_message(output_format)

        # Prepare the user message with prompt and data
        user_message = self._build_user_message(prompt, data)

        log.info(
            "Calling Claude API",
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            output_format=output_format,
        )

        try:
            # Call Claude API
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_message,
                messages=[{"role": "user", "content": user_message}],
            )

            # Extract text from response
            report_content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    report_content += block.text

            log.info(
                "Claude API call successful",
                model=self.model,
                input_tokens=response.usage.input_tokens if hasattr(response, "usage") else 0,
                output_tokens=response.usage.output_tokens if hasattr(response, "usage") else 0,
            )

            return report_content

        except Exception as e:
            log.error("Claude API call failed", error=str(e), model=self.model)
            raise

    def _build_system_message(self, output_format: str) -> str:
        """Build the system message with format instructions.

        Args:
            output_format: Output format - "markdown" or "csv".

        Returns:
            System message string.
        """
        base_message = "You are an expert infrastructure analyst generating reports from Infrahub data."

        if output_format == "markdown":
            format_instructions = """
Output your report in well-formatted markdown with:
- Clear headings and sections
- Tables for structured data
- Bullet points for lists
- Code blocks for technical content
- Professional tone
"""
        else:  # csv
            format_instructions = """
Output your report as a CSV file with:
- First row as headers
- Subsequent rows as data
- Proper CSV formatting (quoted fields if needed)
- Consistent column structure
"""

        mcp_instructions = ""
        if self.mcp_server_url:
            mcp_instructions = f"""
You have access to the Infrahub MCP server at {self.mcp_server_url}.
Use MCP tools to query additional context from Infrahub as needed.
"""

        return base_message + format_instructions + mcp_instructions

    def _build_user_message(self, prompt: str, data: dict[str, Any]) -> str:
        """Build the user message with prompt and data.

        Args:
            prompt: The prompt template.
            data: The input data from GraphQL query.

        Returns:
            User message string.
        """
        # Include the data as JSON for the model to reference
        data_json = json.dumps(data, indent=2)

        message = f"""{prompt}

# Input Data

```json
{data_json}
```

Generate the report based on the above prompt and data.
"""
        return message

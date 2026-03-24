"""AI client for Claude API integration with MCP support."""

from __future__ import annotations

import json
import os
import re
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic
from anthropic.types import ToolParam, ToolResultBlockParam, ToolUseBlock
from mcp import ClientSession
from mcp import types as mcp_types
from mcp.client.streamable_http import streamablehttp_client
from structlog import get_logger

log = get_logger()

MAX_TOOL_USE_ITERATIONS = 15


def _truncate(text: str, max_length: int = 2000) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n... (truncated)"


def _strip_code_fences(text: str) -> str:
    """Extract content from the last markdown code fence block in an LLM response.

    LLMs often wrap output in ```lang ... ``` fences and may prepend explanation
    text.  This function finds the *last* fenced block and returns only its
    inner content.  If no fences are found the original text is returned
    stripped.
    """
    # Find all fenced code blocks (``` optionally followed by a language tag)
    pattern = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
    matches = pattern.findall(text)
    if matches:
        # Use the last match — the actual output when the LLM explains first
        return matches[-1].strip()
    return text.strip()


def _extract_svg(text: str) -> str:
    """Extract SVG content from an LLM response.

    LLMs often wrap SVG in markdown code fences or add preamble/postamble
    text.  This extracts the outermost <svg>...</svg> element.  Falls back
    to _strip_code_fences if no <svg> tag is found.
    """
    match = re.search(r"(<svg\b[^>]*>.*?</svg>)", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return _strip_code_fences(text)


def _extract_csv(text: str) -> str:
    """Extract CSV data from an LLM response that may contain preamble text.

    First tries _strip_code_fences.  If no fences were found, looks for the
    first line containing a comma that doesn't look like prose (i.e. a short
    comma-separated header row) and returns everything from that line onward.
    """
    fenced = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
    if fenced.search(text):
        return _strip_code_fences(text)

    lines = text.strip().splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # CSV header: contains commas, no markdown prefixes, and every
        # comma-separated field is short (< 60 chars) — distinguishes
        # from prose sentences that happen to contain commas.
        if "," in stripped and not stripped.startswith(("#", "-", "*", ">", "`", "|")):
            fields = stripped.split(",")
            if all(len(f.strip()) < 60 for f in fields) and len(fields) >= 2:
                return "\n".join(lines[i:]).strip()

    return text.strip()


def _extract_text(response: Any) -> str:
    """Extract concatenated text from a Claude API response."""
    parts = []
    for block in response.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "".join(parts)


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
        branch: str | None = None,
    ) -> str:
        """Generate a report using Claude API, optionally with MCP tool access.

        When mcp_server_url is configured, connects to the MCP server and runs
        an agentic loop allowing Claude to call tools for additional context.
        Falls back to single-shot generation if MCP connection fails or is not configured.
        """
        if output_format not in ["markdown", "csv", "svg"]:
            raise ValueError(f"Unsupported output format: {output_format}. Must be 'markdown', 'csv', or 'svg'.")

        system_message = self._build_system_message(output_format, branch=branch)
        user_message = self._build_user_message(prompt, data, output_format)

        log.info(
            "Calling Claude API",
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            output_format=output_format,
            mcp_enabled=bool(self.mcp_server_url),
        )
        log.debug("System message", system_message=system_message)
        log.debug("User message", user_message=user_message)

        if self.mcp_server_url:
            async with self._mcp_session() as (tools, session):
                log.info("MCP connected", tool_count=len(tools), url=self.mcp_server_url)
                report_content = await self._run_agentic_loop(
                    system_message=system_message,
                    user_message=user_message,
                    tools=tools,
                    session=session,
                    output_format=output_format,
                )
        else:
            report_content = await self._single_shot_generate(system_message, user_message)

        if output_format == "csv":
            report_content = _extract_csv(report_content)
        elif output_format == "svg":
            report_content = _extract_svg(report_content)

        return report_content

    async def _single_shot_generate(self, system_message: str, user_message: str) -> str:
        """Generate a report with a single Claude API call (no tools)."""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_message,
                messages=[{"role": "user", "content": user_message}],
            )

            report_content = _extract_text(response)

            log.info(
                "Claude API call successful",
                model=self.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

            return report_content

        except Exception as e:
            log.error("Claude API call failed", error=str(e), model=self.model)
            raise

    @asynccontextmanager
    async def _mcp_session(self) -> AsyncIterator[tuple[list[ToolParam], ClientSession]]:
        """Connect to MCP server and yield (anthropic_tools, mcp_session)."""
        url = self.mcp_server_url
        if not url:
            raise ValueError("mcp_server_url is not configured")
        if not url.rstrip("/").endswith("/mcp"):
            url = url.rstrip("/") + "/mcp/"

        async with streamablehttp_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_response = await session.list_tools()

                anthropic_tools: list[ToolParam] = []
                for tool in tools_response.tools:
                    anthropic_tools.append(
                        ToolParam(
                            name=tool.name,
                            description=tool.description or "",
                            input_schema=tool.inputSchema,
                        )
                    )

                log.info("MCP tools discovered", tools=[t["name"] for t in anthropic_tools])
                yield anthropic_tools, session

    async def _execute_tool_call(
        self, tool_use: ToolUseBlock, session: ClientSession
    ) -> ToolResultBlockParam:
        """Execute a single tool call against the MCP server."""
        try:
            result = await session.call_tool(tool_use.name, arguments=tool_use.input)

            text_parts = []
            for content_block in result.content:
                if isinstance(content_block, mcp_types.TextContent):
                    text_parts.append(content_block.text)
                else:
                    text_parts.append(str(content_block))

            return ToolResultBlockParam(
                type="tool_result",
                tool_use_id=tool_use.id,
                content="\n".join(text_parts),
                is_error=bool(result.isError),
            )
        except Exception as exc:
            log.warning("MCP tool call failed", tool=tool_use.name, error=str(exc))
            return ToolResultBlockParam(
                type="tool_result",
                tool_use_id=tool_use.id,
                content=f"Tool execution failed: {exc}",
                is_error=True,
            )

    async def _run_agentic_loop(
        self,
        system_message: str,
        user_message: str,
        tools: list[ToolParam],
        session: ClientSession,
        output_format: str = "markdown",
    ) -> str:
        """Run the agentic tool-use loop. Returns the final report text."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        total_input_tokens = 0
        total_output_tokens = 0

        # Build a short format reminder to inject alongside tool results so the
        # model doesn't lose sight of the output format after many rounds.
        if output_format == "csv":
            _format_reminder = {
                "type": "text",
                "text": "Reminder: when you produce the final output, emit raw CSV only — no explanation, no markdown, no code fences.",
            }
        elif output_format == "svg":
            _format_reminder = {
                "type": "text",
                "text": (
                    "Reminder: when you produce the final output, emit a single valid SVG document only"
                    " — no explanation, no markdown, no code fences. Start with <svg and end with </svg>."
                    " Use only data retrieved from tools or provided in the Input Data."
                ),
            }
        else:
            _format_reminder = None

        for iteration in range(MAX_TOOL_USE_ITERATIONS):
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_message,
                messages=messages,
                tools=tools,
            )

            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            if response.stop_reason != "tool_use":
                log.info(
                    "Agentic report generation complete",
                    iterations=iteration + 1,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                )
                return _extract_text(response)

            # Append assistant message with tool_use blocks
            messages.append({"role": "assistant", "content": response.content})

            # Execute all tool calls
            tool_results: list[ToolResultBlockParam] = []
            for block in response.content:
                if isinstance(block, ToolUseBlock):
                    log.info("Executing MCP tool", tool=block.name, iteration=iteration + 1)
                    result = await self._execute_tool_call(block, session)
                    tool_results.append(result)

            # Include format reminder alongside tool results to keep it fresh
            user_content: list[Any] = list(tool_results)
            if _format_reminder:
                user_content.append(_format_reminder)
            messages.append({"role": "user", "content": user_content})

        # Max iterations reached — make one final call without tools to force text output
        log.warning("Agentic loop reached max iterations", max_iterations=MAX_TOOL_USE_ITERATIONS)
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_message,
            messages=messages,
        )
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        log.info(
            "Agentic report generation complete (max iterations)",
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )
        return _extract_text(response)

    async def generate_attribute_values(
        self,
        attributes: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate attribute values for a FileObject schema using the LLM.

        The LLM is given the schema attribute definitions and context about the
        transform (name, report content, input data) so it can produce meaningful
        values for user-defined attributes.

        Args:
            attributes: List of attribute descriptions (name, kind, description, optional, etc.).
            context: Dict with transform_name, report_content, data, output_format.

        Returns:
            Dict mapping attribute names to generated values.
        """
        attrs_json = json.dumps(attributes, indent=2)
        context_json = json.dumps(
            {
                "transform_name": context.get("transform_name", ""),
                "output_format": context.get("output_format", ""),
                "data_summary": _truncate(json.dumps(context.get("data", {}), indent=2), max_length=2000),
                "report_summary": _truncate(context.get("report_content", ""), max_length=2000),
            },
            indent=2,
        )

        system_message = (
            "You generate metadata attribute values for file objects that store the output of infrastructure data "
            "transforms in Infrahub. Respond with ONLY a valid JSON object mapping attribute names to values. "
            "No markdown fences, no explanation."
        )

        user_message = f"""Generate values for the following attributes of a FileObject that will store a report.

# Attribute Definitions

```json
{attrs_json}
```

# Context

```json
{context_json}
```

Return a JSON object mapping each attribute name to an appropriate value.
For optional attributes, return null if no meaningful value can be determined.
For the "name" attribute (if present), include the transform name and current date/time to ensure uniqueness.
Match the expected type for each attribute kind (Text -> string, Number -> integer, Boolean -> boolean).
"""

        log.info("Calling Claude API for attribute value generation", model=self.model)

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=0.0,
                system=system_message,
                messages=[{"role": "user", "content": user_message}],
            )

            response_text = _extract_text(response)

            cleaned = _strip_code_fences(response_text)
            if not cleaned:
                raise json.JSONDecodeError("Empty response from LLM", response_text, 0)
            result = json.loads(cleaned)

            log.info(
                "Attribute value generation successful",
                model=self.model,
                attributes=list(result.keys()),
            )

            return result

        except (json.JSONDecodeError, Exception) as e:
            log.error("Failed to generate attribute values", error=str(e), model=self.model)
            raise

    def _build_system_message(self, output_format: str, branch: str | None = None) -> str:
        """Build the system message with format instructions."""
        base_message = (
            "You are an expert infrastructure analyst generating reports from Infrahub data. "
            "Output ONLY the report content. No explanations, no commentary, no markdown code fences.\n\n"
            "CRITICAL DATA RULE: You MUST use ONLY the data provided in the Input Data section. "
            "Do not fabricate, invent, or hallucinate any names, values, IP addresses, connections, "
            "or relationships that are not explicitly present in the input data. "
            "If the input data is insufficient, state what is missing rather than inventing values."
        )

        if output_format == "markdown":
            format_instructions = """
Output your report in well-formatted markdown with:
- Clear headings and sections
- Tables for structured data
- Bullet points for lists
- Code blocks for technical content
- Professional tone
"""
        elif output_format == "csv":
            format_instructions = """
Output raw CSV only — no markdown fences, no explanation before or after.
- First row as headers
- Subsequent rows as data
- Proper CSV formatting (quoted fields if needed)
- Consistent column structure
"""
        else:  # svg
            format_instructions = """
Output a single valid SVG document only — no markdown fences, no explanation before or after.
- Start with <svg and end with </svg>
- Include xmlns="http://www.w3.org/2000/svg" on the root element
- Include a viewBox attribute for proper scaling
- Use clean, readable SVG markup
- Use appropriate colors, fonts, and layout for the visualization
- Ensure text elements use legible font sizes
- Every data point in the SVG (names, labels, values, connections) MUST come from the Input Data — do not add fictional elements
"""

        mcp_instructions = ""
        if self.mcp_server_url:
            branch_instruction = ""
            if branch:
                branch_instruction = f'\nIMPORTANT: This transform is running on branch "{branch}". You MUST pass branch="{branch}" to every tool call to ensure you query the correct branch data.\n'
            mcp_instructions = f"""
You have access to tools that can query the Infrahub infrastructure database.
Use these tools to retrieve and verify all data before generating output.
Do not rely on assumptions — query the database for actual values when the input data is incomplete.
Available tool categories: schema discovery, node queries, GraphQL execution, branch management.
After gathering the needed context, produce the final report using only verified data.
{branch_instruction}"""

        return base_message + format_instructions + mcp_instructions

    def _build_user_message(self, prompt: str, data: dict[str, Any], output_format: str = "markdown") -> str:
        """Build the user message with prompt and data."""
        data_json = json.dumps(data, indent=2)

        if output_format == "csv":
            format_reminder = "Output raw CSV only — no markdown, no explanation, no code fences."
        elif output_format == "svg":
            format_reminder = (
                "Output a single valid SVG document only — no markdown, no explanation, no code fences. "
                "Every element in the SVG must correspond to actual data from the Input Data above."
            )
        else:
            format_reminder = "Output the report in well-formatted markdown."

        message = f"""{prompt}

# Input Data

```json
{data_json}
```

Generate the report based on the above prompt and data. {format_reminder}
"""
        return message

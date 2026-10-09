# ruff: noqa: INP001  # standalone script, not a package
"""Find the instruction files and rules that applied to what a session's contexts worked on, but never reached them.

Claude Code's own record in the transcript says what each context loaded, the load log adds what the tracker
saw, and a subagent's result carries the files it quotes back into its parent.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import Layout, glob_to_regex, rule_patterns
from track_reads import (
    DEFAULT_INSTRUCTION_FILES,
    already_loaded,
    claude_md_imports,
    has_claude_md,
    instruction_files,
    load_records,
    read_text,
    reads_agents_md,
    rules,
    skips_project_instructions,
    to_repo_relative,
)

Row = dict[str, Any]
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
# The agents-md hook hands a subdirectory's AGENTS.md to Claude as "Contents of <path>:".
CONTENTS_OF = re.compile(r"Contents of (/\S+?):")
QUOTED_SHARE = 0.8
QUOTED_MIN_LINE = 12
SHOWN = 3


@dataclass
class Context:
    agent: str | None
    label: str
    agent_type: str | None = None
    tool_use_id: str | None = None
    bare: bool = False
    rows: list[Row] = field(default_factory=list)
    read: set[str] = field(default_factory=set)
    changed: set[str] = field(default_factory=set)
    reached: set[str] = field(default_factory=set)
    calls: set[str] = field(default_factory=set)
    """Agent tool calls this context made, to find each subagent's parent."""
    from_results: dict[str, str] = field(default_factory=dict)
    """Files a subagent's result quoted in full into this context, and which subagent."""


@dataclass
class Miss:
    file: str
    why: str
    applies_to: list[str] = field(default_factory=list)


def rows_of(path: Path) -> list[Row]:
    rows = []
    for line in read_text(path).splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def blocks(row: Row) -> list[dict]:
    content = (row.get("message") or {}).get("content")
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def text_of(value: str | list[Any] | dict[str, Any] | None) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(text_of(item) for item in value)
    if isinstance(value, dict):
        return text_of(value.get("text") or value.get("content") or "")
    return ""


def collect(context: Context, project: Path) -> None:
    for row in context.rows:
        attachment = row.get("attachment") or {}
        paths: list[str] = []
        if attachment.get("type") == "instructions":
            paths = [item.get("path", "") for item in attachment.get("files", [])]
        elif attachment.get("type") == "nested_memory":
            paths = [attachment.get("path", "")]
        elif attachment.get("type") == "hook_additional_context":
            paths = CONTENTS_OF.findall(text_of(attachment.get("content")))
        context.reached.update(filter(None, (to_repo_relative(project, path) for path in paths if path)))
        for block in blocks(row) if row.get("type") == "assistant" else []:
            if block.get("type") != "tool_use":
                continue
            if block.get("name") in {"Agent", "Task"}:
                context.calls.add(block.get("id", ""))
            tool_input = block.get("input") or {}
            target = tool_input.get("file_path") or tool_input.get("notebook_path")
            rel = to_repo_relative(project, target) if target else None
            if rel and block.get("name") == "Read":
                context.read.add(rel)
                context.reached.add(rel)
            elif rel and block.get("name") in EDIT_TOOLS:
                context.changed.add(rel)


def contexts_of(transcript: Path, project: Path, log: list[dict], layout: Layout) -> list[Context]:
    main = Context(agent=None, label="main agent", rows=rows_of(transcript))
    contexts = [main]
    for path in sorted((transcript.with_suffix("") / "subagents").glob("agent-*.jsonl")):
        agent_id = path.stem.removeprefix("agent-")
        meta = json.loads(read_text(path.with_suffix(".meta.json")) or "{}")
        agent_type = meta.get("agentType")
        contexts.append(Context(
            agent=agent_id, label=f'{agent_type or "subagent"} "{meta.get("description") or agent_id}"',
            agent_type=agent_type, tool_use_id=meta.get("toolUseId"),
            bare=skips_project_instructions(project, agent_type), rows=rows_of(path),
        ))  # fmt: skip
    for context in contexts:
        collect(context, project)
    for record in log:
        for context in contexts:
            if record["kind"] == "doc" and (
                (record["via"] == "startup" and not context.bare)
                or (record["via"] != "startup" and record.get("agent") == context.agent)
            ):
                context.reached.add(record["path"])
    for subagent in contexts[1:]:
        parent = next((c for c in contexts if subagent.tool_use_id in c.calls), main)
        quote_results(parent, subagent, project, layout)
    return contexts


def result_of(parent: Context, subagent: Context) -> str:
    """A subagent's final result as its parent received it: a task notification or the Agent call's tool result."""
    texts = []
    for row in parent.rows:
        if row.get("type") != "user":
            continue
        body = text_of((row.get("message") or {}).get("content"))
        if subagent.agent and f"<task-id>{subagent.agent}</task-id>" in body:
            texts.append(body)
        texts += [
            text_of(block.get("content"))
            for block in blocks(row)
            if block.get("type") == "tool_result" and block.get("tool_use_id") == subagent.tool_use_id
        ]
    return html.unescape("\n".join(texts))


def quote_results(parent: Context, subagent: Context, project: Path, layout: Layout) -> None:
    result = result_of(parent, subagent)
    for rel in sorted(r for r in subagent.read if layout.is_logged(r)) if result else []:
        lines = [line.strip() for line in read_text(project / rel).splitlines() if len(line.strip()) >= QUOTED_MIN_LINE]
        if lines and sum(line in result for line in lines) >= QUOTED_SHARE * len(lines):
            parent.from_results.setdefault(rel, subagent.label)


def held(context: Context, project: Path, rel: str) -> bool:
    return already_loaded(project, rel, context.reached | set(context.from_results))


def instruction_why(context: Context, project: Path, directory: Path, name: str) -> str:
    folder = f"{directory.as_posix()}/"
    read_below = any(rel.startswith(folder) for rel in context.read)
    on_read = (
        f"Claude Code loads it on a Read below {folder}, and this context only wrote there"
        if not read_below
        else f"a file below {folder} was read, yet neither Claude Code's record nor the log shows it loading"
    )
    if name == "CLAUDE.md":
        return on_read
    beside = (directory / "CLAUDE.md").as_posix()
    rel = (directory / name).as_posix()
    if (project / beside).is_file() and any(path == rel for path, _ in claude_md_imports(project, beside, {beside})):
        return on_read
    mode = instruction_files()
    if reads_agents_md(project, mode):
        if mode == "claude-md-and-agents-md" or not has_claude_md(project / directory):
            return on_read
        return f"{folder} has its own CLAUDE.md, so Claude Code reads that instead of this AGENTS.md"
    cause = (
        f"the repository has a root CLAUDE.md, so the {mode} setting reads no AGENTS.md below it"
        if mode == DEFAULT_INSTRUCTION_FILES
        else f"the {mode} setting reads no AGENTS.md"
    )
    return f"Claude Code never loads it on its own: {cause}, and no CLAUDE.md in {folder} imports it"


def misses_of(context: Context, project: Path, startup: list[str]) -> list[Miss]:
    touched = sorted(context.read | context.changed)
    misses: dict[str, Miss] = {}
    if context.bare and touched:
        missing = [rel for rel in startup if not held(context, project, rel)]
        if missing:
            misses["startup"] = Miss(
                ", ".join(missing),
                f"{context.agent_type} subagents start without project instructions",
                ["session start"],
            )
    for rel in touched:
        for directory in list(reversed(Path(rel).parents))[1:]:
            for name in ("CLAUDE.md", "AGENTS.md"):
                instruction = (directory / name).as_posix()
                if (project / instruction).is_file() and not held(context, project, instruction):
                    why = instruction_why(context, project, directory, name)
                    misses.setdefault(instruction, Miss(instruction, why)).applies_to.append(rel)
    visible = set()
    for rule, patterns in rules(project):
        visible.add(rule)
        applies = [rel for rel in touched if patterns and any(glob_to_regex(p).match(rel) for p in patterns)]
        if applies and not held(context, project, rule):
            why = (
                "Claude Code injects a rule only when a matching file is read, and this context only wrote those files"
                if not any(rel in context.read for rel in applies)
                else "a matching file was read, yet neither Claude Code's record nor the log shows the rule loading"
            )
            misses[rule] = Miss(rule, why, applies)
    hidden = project / ".agents" / "rules"
    for path in sorted(hidden.rglob("*.md")) if hidden.is_dir() else []:
        unseen = to_repo_relative(project, path)
        patterns = rule_patterns(read_text(path))
        applies = [rel for rel in touched if not patterns or any(glob_to_regex(p).match(rel) for p in patterns)]
        if unseen and unseen not in visible and applies:
            misses[unseen] = Miss(
                unseen,
                "it is in .agents/rules, not .claude/rules, and Claude Code reads nothing under .agents/",
                applies,
            )
    return list(misses.values())


def write_not_loaded(path: Path, transcript: Path, project: Path, log_path: Path, layout: Layout) -> int:
    """Write not-loaded.md for the doctor and return how many items it lists."""
    log = load_records(log_path)
    project = Path(project).resolve()
    contexts = contexts_of(transcript, project, log, layout)
    startup = [r["path"] for r in log if r["kind"] == "doc" and r["via"] == "startup"]
    lines = [
        f"# Not loaded · {transcript.stem}",
        "",
        "Instruction files and rules that applied to what a context read or changed, but never reached that "
        "context, per Claude Code's own record in the transcript and the load log. Every item belongs in the "
        "report's Not loaded section, confirmed or explained away.",
    ]
    count = 0
    for context in contexts:
        misses = misses_of(context, project, startup)
        if not misses:
            continue
        count += len(misses)
        note = " · starts without project instructions" if context.bare else ""
        lines += ["", f"## {context.label}{note}", ""]
        for miss in misses:
            shown = ", ".join(miss.applies_to[:SHOWN]) + (
                f" and {len(miss.applies_to) - SHOWN} more" if len(miss.applies_to) > SHOWN else ""
            )
            lines.append(f"- `{miss.file}` · applies to {shown} · {miss.why}")
    if not count:
        lines += [
            "",
            "Nothing: every instruction file and rule that applied to a touched file reached the context that touched it.",
        ]
    quoted = [(c, rel, source) for c in contexts for rel, source in sorted(c.from_results.items())]
    if quoted:
        lines += ["", "## Reached only through a subagent's result", ""]
        lines += [f"- {c.label}: `{rel}`, quoted in full by {source}'s result" for c, rel, source in quoted]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count

# ruff: noqa: INP001  # standalone hook script, not a package
"""Claude Code hook: record which internal docs a session reads, and what led to each one.

The context plugin registers it in hooks/hooks.json for UserPromptSubmit, PreToolUse (Skill, Agent),
SubagentStart, PostToolUse (Read) and SessionEnd; it dispatches on the event name.

Every dev/ or .agents/ read, path-scoped rule, and nested CLAUDE.md load is recorded with:

- parents: for a rule or nested CLAUDE.md, the file whose Read loaded it (certain); for a doc, the
  files already loaded this session that name its path, which is where the path could have come from,
  not necessarily why it was read (the prompt usually is; context_map.py works that out)
- context: the prompt and subagent it happened under; skills are logged in sequence, not as parents

Output goes to a doc-reads/ directory in the session's own directory, beside subagents/ and
tool-results/ (~/.claude/projects/<project>/<session_id>/doc-reads/), or to
CLAUDE_TRACK_DOC_READS_DIR/<session_id>/ when that is set. reads.jsonl holds the records, reads.log is
the readable log, and state.json tracks what the log already shows. New log lines are echoed into the
chat unless CLAUDE_TRACK_DOC_READS_ECHO=0. At session end a summary goes to the log, the terminal, and
$GITHUB_STEP_SUMMARY when set.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

DOC_PATH = re.compile(r"(^|/)(dev|\.agents)/")
MARKDOWN_LINK_TARGET = re.compile(r"\]\(([^)#\s]+)")
# Code spans and emails are not imports; an @ must start a token.
CLAUDE_MD_IMPORT = re.compile(r"(?:^|\s)@([\w./-]+)")
AGENT_TOOLS = {"Agent", "Task"}
PREVIEW_CHARS = 100
FALLBACK_DIR = Path.home() / ".claude" / "doc-reads"
"""Only used when an event carries no transcript path, or cannot be parsed."""
ICONS = {"read": "📄 read", "rule": "📏 rule", "claude-md": "📘 loaded", "import": "📘 loaded"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def preview(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= PREVIEW_CHARS else flat[: PREVIEW_CHARS - 1] + "…"


def to_repo_relative(project: Path, path: str | Path) -> str | None:
    resolved = Path(os.path.realpath(path))
    try:
        return resolved.relative_to(project).as_posix()
    except ValueError:
        return None


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def load_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in read_text(path).splitlines() if line.strip()]


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a rule's `paths:` glob, where `**` spans directories and `*` does not."""
    parts = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            parts.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            parts.append(".*")
            i += 2
        elif pattern[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(parts) + r"\Z")


def rule_patterns(text: str) -> list[str]:
    """Return a rule's `paths:` globs; an empty list means the rule loads at startup."""
    if not text.startswith("---\n"):
        return []
    frontmatter = text[4 : text.find("\n---", 4)]
    patterns: list[str] = []
    in_paths = False
    for line in frontmatter.splitlines():
        if inline := re.match(r"paths:\s*[\"']?([^\"'\s]+)[\"']?\s*$", line):
            patterns.append(inline.group(1))
        elif re.match(r"paths:\s*$", line):
            in_paths = True
        elif in_paths and (item := re.match(r"\s*-\s*[\"']?(.*?)[\"']?\s*$", line)):
            patterns.append(item.group(1))
        else:
            in_paths = False
    return patterns


def rules(project: Path) -> Iterator[tuple[str, list[str]]]:
    for rule in sorted((project / ".claude" / "rules").rglob("*.md")):
        rule_rel = to_repo_relative(project, rule)
        if rule_rel:
            yield rule_rel, rule_patterns(read_text(rule))


def claude_md_imports(project: Path, md_rel: str, seen: set[str]) -> Iterator[tuple[str, str]]:
    """Yield (imported, importer) for each file a CLAUDE.md pulls in with @path, recursively."""
    md_dir = (project / md_rel).parent
    for target in CLAUDE_MD_IMPORT.findall(read_text(project / md_rel)):
        candidate = md_dir / target
        imported = to_repo_relative(project, candidate) if candidate.is_file() else None
        if imported and imported not in seen:
            seen.add(imported)
            yield imported, md_rel
            yield from claude_md_imports(project, imported, seen)


def find_mention(text: str, base_dir: Path, child_rel: str) -> tuple[int, str] | None:
    """Return the 1-based line and style ("path" or "link") of the first place text names child_rel.

    A path counts when it is repo-relative; a Markdown link counts when its target, resolved against
    base_dir, is child_rel.
    """
    path_pattern = re.compile(rf"(?<![\w./-]){re.escape(child_rel)}(?![\w/-])")
    for number, line in enumerate(text.splitlines(), start=1):
        if path_pattern.search(line):
            return number, "path"
        if any(os.path.normpath(base_dir / target) == child_rel for target in MARKDOWN_LINK_TARGET.findall(line)):
            return number, "link"
    return None


def mentions_path(text: str, base_dir: Path, child_rel: str) -> bool:
    return find_mention(text, base_dir, child_rel) is not None


def mentions(project: Path, parent_rel: str, child_rel: str) -> bool:
    return mentions_path(read_text(project / parent_rel), Path(parent_rel).parent, child_rel)


def line_range(tool_input: dict) -> str | None:
    offset, limit = tool_input.get("offset"), tool_input.get("limit")
    if offset is None and limit is None:
        return None
    start = int(offset or 1)
    return f"lines {start}-{start + int(limit) - 1}" if limit else f"from line {start}"


def doc(path: str, via: str, link: str, parents: list[str], context: list[str], **extra: object) -> dict:
    return {"kind": "doc", "ts": now(), "path": path, "via": via, "link": link, "parents": parents,
            "context": context, **extra}  # fmt: skip


def startup_records(project: Path) -> list[dict]:
    records = []
    if (project / "CLAUDE.md").is_file():
        records.append(doc("CLAUDE.md", "startup", "startup", [], []))
        records.extend(
            doc(imported, "startup", "import", [importer], [])
            for imported, importer in claude_md_imports(project, "CLAUDE.md", {"CLAUDE.md"})
        )
    records.extend(doc(rule, "startup", "startup", [], []) for rule, patterns in rules(project) if not patterns)
    return records


def next_id(records: list[dict], kind: str, prefix: str) -> str:
    return f"{prefix}{sum(1 for r in records if r['kind'] == kind) + 1}"


def prompt_record(event: dict, records: list[dict], text: str) -> dict:
    return {"kind": "prompt", "id": next_id(records, "prompt", "p"), "ts": now(),
            "prompt_id": event.get("prompt_id"), "text": text}  # fmt: skip


def missing_prompt(event: dict, records: list[dict]) -> list[dict]:
    """Stand in for a prompt submitted before tracking started, so its events still group together."""
    prompt_id = event.get("prompt_id")
    if not prompt_id or any(r["kind"] == "prompt" and r["prompt_id"] == prompt_id for r in records):
        return []
    return [prompt_record(event, records, "(prompt not recorded)")]


def link_agent(records: list[dict], agent_id: str, agent_type: str | None) -> dict:
    """Tie a subagent's id to the Agent call that started it, which the hook input does not name."""
    linked = {r["call"] for r in records if r["kind"] == "agent-link"}
    unlinked = [r for r in records if r["kind"] == "agent" and r["id"] not in linked]
    same_type = [r for r in unlinked if agent_type and r["subagent_type"] == agent_type]
    if same_type:
        call, how = same_type[0], "type-match"
    elif unlinked:
        call, how = unlinked[0], "oldest-unlinked"
    else:
        call, how = None, "unmatched"
    return {"kind": "agent-link", "ts": now(), "agent_id": agent_id, "agent_type": agent_type,
            "call": call["id"] if call else None, "how": how}  # fmt: skip


def missing_agent_link(event: dict, records: list[dict]) -> list[dict]:
    agent_id = event.get("agent_id")
    if agent_id and not any(r["kind"] == "agent-link" and r["agent_id"] == agent_id for r in records):
        return [link_agent(records, agent_id, event.get("agent_type"))]
    return []


def current_context(event: dict, records: list[dict]) -> list[str]:
    """Return the ids of the prompt and subagent an event happens under, outermost first."""
    prompts = [r for r in records if r["kind"] == "prompt"]
    prompt_id = event.get("prompt_id")
    matching = [r for r in prompts if prompt_id and r["prompt_id"] == prompt_id]
    base = [(matching or prompts)[-1]["id"]] if prompts else []
    agent_id = event.get("agent_id")
    if not agent_id:
        return base
    link = next((r for r in records if r["kind"] == "agent-link" and r["agent_id"] == agent_id), None)
    call = next((r for r in records if link and link["call"] and r.get("id") == link["call"]), None)
    return [*call["context"], call["id"]] if call else [*base, f"agent:{agent_id}"]


def on_tool_start(event: dict, records: list[dict]) -> list[dict]:
    tool_input = event.get("tool_input", {})
    context = current_context(event, records)
    if event.get("tool_name") == "Skill":
        return [{"kind": "skill", "id": next_id(records, "skill", "s"), "ts": now(),
                 "name": tool_input.get("skill", "?"), "args": tool_input.get("args", ""), "context": context}]  # fmt: skip
    if event.get("tool_name") in AGENT_TOOLS:
        return [{"kind": "agent", "id": next_id(records, "agent", "a"), "ts": now(),
                 "subagent_type": tool_input.get("subagent_type", "general-purpose"),
                 "description": tool_input.get("description", ""), "prompt": tool_input.get("prompt", ""),
                 "tool_use_id": event.get("tool_use_id"), "context": context}]  # fmt: skip
    return []


def on_read(event: dict, project: Path, records: list[dict]) -> list[dict]:
    tool_input = event.get("tool_input", {})
    read_rel = to_repo_relative(project, tool_input.get("file_path", ""))
    if read_rel is None:
        return []
    context = current_context(event, records)
    agent = event.get("agent_id")
    about = {"agent": agent, "tool_use_id": event.get("tool_use_id")}
    # Claude Code loads a rule or nested CLAUDE.md once per context, and a subagent is its own context.
    loaded = {r["path"] for r in records if r["kind"] == "doc" and (r["via"] == "startup" or r.get("agent") == agent)}
    new: list[dict] = []

    def add(entry: dict) -> None:
        loaded.add(entry["path"])
        new.append(entry)

    if DOC_PATH.search(read_rel):
        # Every Read is recorded; repeat counts this context's reads of the file, including this one.
        repeat = 1 + sum(
            1 for r in records if r["kind"] == "doc" and r["via"] == "read" and r["path"] == read_rel
            and r.get("agent") == agent
        )  # fmt: skip
        candidates = list(dict.fromkeys(r["path"] for r in records if r["kind"] == "doc" and r["path"] != read_rel))
        parents = [path for path in candidates if mentions(project, path, read_rel)]
        add(doc(read_rel, "read", "referenced" if parents else "none", parents, context,
                lines=line_range(tool_input), repeat=repeat, **about))  # fmt: skip

    for directory in list(reversed(Path(read_rel).parents))[1:]:
        md_rel = (directory / "CLAUDE.md").as_posix()
        if md_rel not in loaded and (project / md_rel).is_file():
            add(doc(md_rel, "claude-md", "claude-md", [read_rel], context, **about))
            for imported, importer in claude_md_imports(project, md_rel, set(loaded)):
                add(doc(imported, "claude-md", "import", [importer], context, **about))

    for rule_rel, patterns in rules(project):
        if rule_rel not in loaded and any(glob_to_regex(p).match(read_rel) for p in patterns):
            add(doc(rule_rel, "rule", "rule-match", [read_rel], context, **about))

    return new


def context_label(context_id: str, records: list[dict]) -> str:
    if context_id.startswith("agent:"):
        agent_id = context_id.removeprefix("agent:")
        link = next((r for r in records if r["kind"] == "agent-link" and r["agent_id"] == agent_id), {})
        return f"🤖 agent {link.get('agent_type') or agent_id} (start not recorded)"
    entry = next(r for r in records if r.get("id") == context_id)
    if entry["kind"] == "prompt":
        return f'💬 prompt {context_id}: "{preview(entry["text"])}"'
    return f'🤖 agent {entry["subagent_type"]}: "{preview(entry["description"])}"'


def entry_label(entry: dict) -> str:
    if entry["kind"] == "skill":
        return f"🧩 skill {entry['name']}" + (f" {preview(entry['args'])}" if entry["args"] else "")
    line = f"{ICONS[entry['via']]} {entry['path']}"
    if entry.get("lines"):
        line += f" ({entry['lines']})"
    if entry.get("repeat", 1) > 1:
        line += f" (read {entry['repeat']})"
    if entry["parents"] and entry["via"] == "read":
        line += " · path via " + ", ".join(entry["parents"])
    elif entry["parents"]:
        line += " ← " + ", ".join(entry["parents"])
    return line


def is_logged(entry: dict) -> bool:
    return entry["kind"] == "skill" or (entry["kind"] == "doc" and entry["via"] != "startup")


def render(entries: list[dict], records: list[dict], last_context: list[str]) -> tuple[list[str], list[str]]:
    """Indent each entry under its context, repeating a context header only when the context changes."""
    lines: list[str] = []
    for entry in entries:
        context = entry["context"]
        shared = 0
        while shared < min(len(context), len(last_context)) and context[shared] == last_context[shared]:
            shared += 1
        lines.extend("  " * depth + context_label(context[depth], records) for depth in range(shared, len(context)))
        lines.append("  " * len(context) + entry_label(entry))
        last_context = context
    return lines, last_context


def is_first(entry: dict) -> bool:
    return entry.get("repeat", 1) == 1


def summary(records: list[dict]) -> list[str]:
    docs = [r for r in records if r["kind"] == "doc" and r["via"] != "startup"]
    if not docs:
        return []
    unique = len({(r.get("agent"), r["path"]) for r in docs})
    startup = ", ".join(r["path"] for r in records if r["kind"] == "doc" and r["via"] == "startup")
    lines, _ = render([r for r in records if is_logged(r)], records, [])
    return [f"── docs read this session ({unique} files, {len(docs)} loads) ──", f"startup: {startup}", *lines]


@contextlib.contextmanager
def locked(directory: Path) -> Iterator[None]:
    """Hold an exclusive lock on the output directory; closing the descriptor releases it."""
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def output_dir(event: dict) -> Path:
    """Where a session's records go.

    Recomputed on every event, because the session directory moves with the transcript, for example
    when the session switches into a worktree.
    """
    override = os.environ.get("CLAUDE_TRACK_DOC_READS_DIR")
    if override:
        return Path(override) / event["session_id"]
    if transcript := event.get("transcript_path"):
        return Path(transcript).with_suffix("") / "doc-reads"
    return FALLBACK_DIR / event["session_id"]


def start_log(log_path: Path, project: Path, session_id: str) -> None:
    log_path.write_text(f"# Claude session {session_id} in {project}, started {now()}\n", encoding="utf-8")


def emit_summary(lines: list[str], log_path: Path) -> None:
    with log_path.open("a", encoding="utf-8") as log:
        log.write("\n".join(["", *lines, ""]) + "\n")
    # No controlling terminal in CI or headless runs; the log and step summary still get it.
    with contextlib.suppress(OSError):
        Path("/dev/tty").write_text("\n".join([*lines, f"log: {log_path}", ""]) + "\n", encoding="utf-8")
    if step_summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(step_summary).open("a", encoding="utf-8") as out:
            out.write("\n".join([f"### {lines[0].strip('─ ')}", "", "```", *lines[1:], "```", ""]) + "\n")


def main() -> None:
    directory = FALLBACK_DIR
    # Top-level boundary: a tracking failure is recorded, never surfaced as a hook error on every tool call.
    try:
        event = json.load(sys.stdin)
        directory = output_dir(event)
        directory.mkdir(parents=True, exist_ok=True)
        track(event, directory)
    except Exception:
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "errors.log").open("a", encoding="utf-8") as errors:
            errors.write(f"{now()}\n{traceback.format_exc()}\n")


def track(event: dict, directory: Path) -> None:
    hook = event.get("hook_event_name")
    session_id = event["session_id"]
    project = Path(os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR", event.get("cwd", "."))))
    # Parallel tool calls run this hook concurrently; the lock serialises each read-modify-append.
    with locked(directory):
        records_path = directory / "reads.jsonl"
        log_path = directory / "reads.log"
        state_path = directory / "state.json"
        records = load_records(records_path)
        new = [] if records else startup_records(project)
        if not records:
            start_log(log_path, project, session_id)

        if hook == "UserPromptSubmit":
            new.append(prompt_record(event, records + new, event.get("prompt", "")))
        else:
            new += missing_prompt(event, records + new)
            new += missing_agent_link(event, records + new)
        if hook == "PreToolUse":
            new += on_tool_start(event, records + new)
        elif hook == "PostToolUse" and event.get("tool_name") == "Read":
            new += on_read(event, project, records + new)
        with records_path.open("a", encoding="utf-8") as handle:
            handle.writelines(json.dumps(entry, ensure_ascii=False) + "\n" for entry in new)
        records += new

        state = json.loads(read_text(state_path) or "{}")
        pending = [r for r in records[state.get("logged", 0) :] if is_logged(r)]
        lines, state["last_context"] = render(pending, records, state.get("last_context", []))
        # The chat notice only announces a file the first time, so repeated reads do not flood it.
        echo, state["echo_context"] = render(
            [r for r in pending if is_first(r)], records, state.get("echo_context", [])
        )
        state["logged"] = len(records)
        state_path.write_text(json.dumps(state), encoding="utf-8")
        if lines:
            clock = time.strftime("%H:%M:%S")
            with log_path.open("a", encoding="utf-8") as log:
                log.writelines(f"{clock} {line}\n" for line in lines)

        if hook == "SessionEnd" and (closing := summary(records)):
            emit_summary(closing, log_path)

    # UserPromptSubmit stdout would enter the model's context; only PostToolUse output is a user-facing notice.
    if hook == "PostToolUse" and echo and os.environ.get("CLAUDE_TRACK_DOC_READS_ECHO", "1") != "0":
        print(json.dumps({"systemMessage": "\n".join(echo)}))


if __name__ == "__main__":
    main()

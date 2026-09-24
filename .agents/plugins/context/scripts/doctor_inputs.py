#!/usr/bin/env python3
"""Write the context doctor's summary.md and index.md for a session, then print where they and its log are."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from operator import attrgetter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from config import Layout, load_layout, rule_patterns
from not_loaded import write_not_loaded
from track_reads import clock, read_text, startup_records

if TYPE_CHECKING:
    from collections.abc import Iterator

Row = dict[str, Any]

HOME = Path.home()
CONFIG_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR") or HOME / ".claude")
PROJECTS = HOME / ".claude" / "projects"
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
GUIDANCE_SUFFIXES = {".md", ".mdx", ".rst"}
PRUNE = {
    "node_modules", ".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", "dist",
    "build",
}  # fmt: skip
SKIP_PROMPT = (
    "<local-command-caveat>",
    "<local-command-stdout>",
    "<command-message>",
    "Caveat:",
    "[Request interrupted",
)
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
COMMAND = re.compile(r"<command-name>(/[^<]+)</command-name>.*?<command-args>(.*?)</command-args>", re.DOTALL)
PROMPT_CHARS = 700
REPLY_CHARS = 600
# A long session gets shorter replies so the summary stays readable next to the corpus.
LONG_SESSION_TURNS = 120
LONG_SESSION_REPLY_CHARS = 300
LATEST_COMPACTION_CHARS = 16000
EARLIER_COMPACTION_CHARS = 5000
KILO = 1000


def tok(text: str | None) -> int:
    return len(text or "") // 4


def fmt(n: int) -> str:
    return f"{n / KILO:.1f}k" if n >= KILO else str(n)


def short(text: str | None, n: int) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= n else flat[: n - 1] + "…"


def local_time(ts: str) -> str:
    return clock(ts, "%m-%d %H:%M:%S")


def text_of(content: str | list[Row] | None) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(x.get("text", "") for x in content if isinstance(x, dict) and x.get("type") == "text")


def find_transcript(project_dir: str, session_id: str) -> Path:
    direct = PROJECTS / re.sub(r"[^A-Za-z0-9-]", "-", project_dir) / f"{session_id}.jsonl"
    if direct.exists():
        return direct
    hits = sorted(PROJECTS.glob(f"*/{session_id}.jsonl"))
    if not hits:
        sys.exit(f"No transcript found for session {session_id} under {PROJECTS}")
    return hits[0]


def repo_relative(path: str, root: str) -> str:
    """Repo-relative path, tagged with the worktree name when the file sits in a nested worktree."""
    if path.startswith(root + "/.claude/worktrees/"):
        name, _, rel = path[len(root) + len("/.claude/worktrees/") :].partition("/")
        return f"{rel} ({name})"
    if path.startswith(root + "/"):
        return path[len(root) + 1 :]
    return path.replace(str(HOME), "~", 1)


def is_guidance(rel: str, layout: Layout) -> bool:
    path = rel.split(" (", maxsplit=1)[0]
    return path.startswith((".claude/", "~/")) or path.endswith("CLAUDE.md") or layout.is_logged(path)


def load_rows(path: Path) -> list[Row]:
    rows = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


@dataclass
class Agent:
    label: str
    rows: list[Row]
    first: str = ""


def load_session(transcript: Path) -> list[Agent]:
    subagents = []
    subdir = transcript.with_suffix("") / "subagents"
    for path in sorted(subdir.glob("agent-*.jsonl")) if subdir.exists() else []:
        meta = path.with_suffix(".meta.json")
        description = json.loads(meta.read_text()).get("description", "") if meta.exists() else ""
        rows = load_rows(path)
        first = next((r.get("timestamp", "") for r in rows if r.get("timestamp")), "")
        subagents.append(Agent(f"subagent: {description or path.stem}", rows, first))
    return [Agent("main agent", load_rows(transcript)), *sorted(subagents, key=attrgetter("first"))]


@dataclass
class Turn:
    ts: str
    prompt: str
    reply: str = ""
    result: bool = False
    """A background subagent's result arriving in the main agent, not something the user typed."""


def prompt_turns(rows: list[Row]) -> list[Turn]:
    """Each prompt you typed, paired with the last thing the agent said before the next one."""
    turns: list[Turn] = []
    for r in rows:
        if r.get("type") == "user" and not r.get("isMeta") and not r.get("isCompactSummary"):
            content = r.get("message", {}).get("content")
            if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                continue
            body = text_of(content).strip()
            if (r.get("origin") or {}).get("kind") == "task-notification" or body.startswith("<task-notification>"):
                summary = re.search(r"<summary>(.*?)</summary>", body, re.DOTALL)
                label = summary.group(1).strip() if summary else "a background task finished"
                turns.append(
                    Turn(
                        r.get("timestamp", ""),
                        f"{label} ({len(body)} chars; not-loaded.md lists what it quoted)",
                        result=True,
                    )
                )
                continue
            if command := COMMAND.search(body):
                body = f"{command.group(1)} {command.group(2)}".strip()
            elif not body or body.startswith(SKIP_PROMPT):
                continue
            turns.append(Turn(r.get("timestamp", ""), body))
        elif r.get("type") == "assistant" and turns and (said := text_of(r.get("message", {}).get("content")).strip()):
            turns[-1].reply = said
    return turns


@dataclass
class Touched:
    changed: dict[str, list[str]] = field(default_factory=dict)
    read: Counter[str] = field(default_factory=Counter)


def touched_files(agents: list[Agent], root: str, layout: Layout) -> Touched:
    """Files each agent edited, and the non-guidance directories it read from."""
    touched = Touched()
    for agent in agents:
        for r in agent.rows:
            content = r.get("message", {}).get("content") if r.get("type") == "assistant" else None
            for block in content if isinstance(content, list) else []:
                tool_input = (block.get("input") or {}) if isinstance(block, dict) else {}
                target = tool_input.get("file_path") or tool_input.get("notebook_path")
                if not (isinstance(block, dict) and block.get("type") == "tool_use" and target):
                    continue
                rel = repo_relative(target, root)
                if block.get("name") in EDIT_TOOLS:
                    touched.changed.setdefault(rel, []).append(f"{local_time(r.get('timestamp', ''))} {agent.label}")
                elif block.get("name") == "Read" and not is_guidance(rel, layout):
                    touched.read["/".join(rel.split(" (")[0].split("/")[:3])] += 1
    return touched


def write_summary(path: Path, session_id: str, agents: list[Agent], root: str, layout: Layout) -> None:
    main = agents[0].rows
    stamped = [r["timestamp"] for a in agents for r in a.rows if r.get("timestamp")]
    compactions = [
        local_time(r.get("timestamp", ""))
        for r in main
        if r.get("type") == "system" and r.get("subtype") == "compact_boundary"
    ]
    lines = [
        f"# Session summary · {session_id}",
        "",
        f"Span (local time): {local_time(min(stamped)) if stamped else '?'} → {local_time(max(stamped)) if stamped else '?'}",
        f"Working directories: {', '.join(dict.fromkeys(r['cwd'] for r in main if r.get('cwd'))) or '?'}",
        f"Git branches: {', '.join(dict.fromkeys(r['gitBranch'] for r in main if r.get('gitBranch'))) or '?'}",
        f"Subagents: {len(agents) - 1}",
        f"Compactions of the main agent (local time): {', '.join(compactions) or 'none'}",
        "",
        "Built from the transcript, not written by a model: your prompts with the reply that followed, background "
        "subagent results as they arrived, compaction summaries, files changed and areas read.",
        "",
        "## Prompts and replies (main agent)",
        "",
    ]
    turns = prompt_turns(main)
    reply_chars = LONG_SESSION_REPLY_CHARS if len(turns) > LONG_SESSION_TURNS else REPLY_CHARS
    for turn in turns:
        who = "subagent result" if turn.result else "you"
        lines.append(f"- **{local_time(turn.ts)}** {who}: {short(turn.prompt, PROMPT_CHARS)}")
        if turn.reply:
            lines.append(f"  - agent: {short(turn.reply, reply_chars)}")

    summaries = [
        (r.get("timestamp", ""), text_of(r.get("message", {}).get("content")))
        for r in main
        if r.get("isCompactSummary")
    ]
    if summaries:
        lines += ["", "## Compaction summaries", ""]
    for i, (ts, body) in enumerate(summaries):
        limit = LATEST_COMPACTION_CHARS if i == len(summaries) - 1 else EARLIER_COMPACTION_CHARS
        lines += [f"### {local_time(ts)}", "", body[:limit] + ("\n\n[…truncated]" if len(body) > limit else ""), ""]

    touched = touched_files(agents, root, layout)
    lines += ["", "## Files changed (Edit/Write)", ""]
    lines += [f"- {rel}: {len(edits)} edits, first {edits[0]}" for rel, edits in touched.changed.items()] or [
        "- none recorded"
    ]
    lines += ["", "## Areas read (code and other files, by directory)", ""]
    lines += [f"- {area}: {n} reads" for area, n in touched.read.most_common(40)] or ["- none recorded"]
    if len(agents) > 1:
        lines += ["", "## Subagents", ""]
    for agent in agents[1:]:
        first = next((r for r in agent.rows if r.get("type") == "user"), {})
        brief = short(text_of(first.get("message", {}).get("content")), PROMPT_CHARS)
        lines.append(f"- **{local_time(agent.first)}** {agent.label}: {brief}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def walk(root: Path, skip: set[Path] | None = None) -> Iterator[Path]:
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in PRUNE and Path(directory) / d not in (skip or set()))
        for name in sorted(files):
            yield Path(directory) / name


def frontmatter(text: str) -> tuple[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    return (match.group(1), match.group(2)) if match else ("", text)


def frontmatter_field(fm: str, name: str) -> str:
    match = re.search(rf"^{name}:\s*(.+)$", fm, re.MULTILINE)
    return match.group(1).strip().strip("'\"") if match else ""


def repo_path(path: Path, docs_root: Path) -> str:
    """The path as the tracker logs it: repo-relative after symlinks resolve."""
    try:
        return path.resolve().relative_to(docs_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def startup_paths(docs_root: Path) -> list[str]:
    return [record["path"] for record in startup_records(docs_root)]


def load_list(docs_root: Path, layout: Layout) -> list[tuple[str, int]]:
    """Every doc the layout names, except what loads at session start and the rule and skill directories."""
    startup = set(startup_paths(docs_root))
    index_only = [
        (docs_root / folder / kind).resolve()
        for folder in (".claude", ".agents")
        for kind in ("rules", "skills")
        if (docs_root / folder / kind).exists()
    ]
    skip = {docs_root / directory for directory in layout.skip_dirs} | {docs_root / ".claude" / "worktrees"}
    entries = []
    for path in walk(docs_root, skip=skip):
        rel = path.relative_to(docs_root).as_posix()
        if rel in startup or not layout.is_doc(rel) or path.suffix not in GUIDANCE_SUFFIXES:
            continue
        if any(path.resolve().is_relative_to(directory) for directory in index_only):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if text.strip():
            entries.append((rel, tok(text)))
    return entries


def rule_lines(docs_root: Path, seen: set[Path]) -> list[str]:
    lines = []
    for base in (".claude/rules", ".agents/rules"):
        # Claude Code reads nothing under .agents/, so a rule there loads only through .claude/rules.
        unseen = "" if base == ".claude/rules" else " · not in .claude/rules, so Claude Code never loads it"
        for path in sorted((docs_root / base).rglob("*.md")):
            if path.resolve() in seen:
                continue
            seen.add(path.resolve())
            text = path.read_text(encoding="utf-8", errors="replace")
            _, body = frontmatter(text)
            globs = rule_patterns(text)
            heading = next((x.lstrip("# ").strip() for x in body.splitlines() if x.startswith("#")), path.stem)
            first = next((x.strip() for x in body.splitlines() if x.strip() and not x.startswith("#")), "")
            scope = ("paths: " + ", ".join(globs)) if globs else "no paths: (loaded at every session start)"
            lines.append(
                f"- {repo_path(path, docs_root)} (≈{fmt(tok(body))}) · {scope} · {heading}: {short(first, 160)}{unseen}"
            )
    return lines


def session_skills(rows: list[Row]) -> list[str]:
    """The skills Claude Code offered the session, from its skill-listing attachments."""
    names: dict[str, None] = {}
    for row in rows:
        attachment = row.get("attachment") or {}
        if attachment.get("type") == "skill_listing":
            names.update(dict.fromkeys(attachment.get("names") or []))
    return list(names)


def plugin_roots(root: str) -> dict[str, Path]:
    """Each plugin's folder by plugin name: an install for this project first, then a user one, then a synced one."""
    plugins = CONFIG_DIR / "plugins"
    installed = json.loads(read_text(plugins / "installed_plugins.json") or "{}")
    ranked = []
    for key, installs in (installed.get("plugins") or {}).items():
        for install in installs:
            path = Path(install.get("installPath") or "/nonexistent")
            if path.is_dir():
                ranked.append((0 if install.get("projectPath") == root else 1, key.partition("@")[0], path))
    ranked += [(2, path.name, path) for path in sorted(plugins.glob("synced/*/*")) if path.is_dir()]
    roots: dict[str, Path] = {}
    for _, name, path in sorted(ranked):
        roots.setdefault(name, path)
    return roots


def skill_file(name: str, bases: dict[str, list[Path]]) -> Path | None:
    """A skill's file, looked up under its plugin's folder, or under the project's and user's for a bare name."""
    plugin, _, skill = name.rpartition(":")
    for base in bases.get(plugin, []):
        found = [*sorted(base.glob(f"skills/**/{skill}/SKILL.md")), base / "commands" / f"{skill}.md"]
        if match := next((path for path in found if path.is_file()), None):
            return match
    return None


def skill_line(name: str, path: Path | None, note: str = "") -> str:
    if path is None:
        return f"- {name} · built in, or installed where this script does not look"
    _, body = frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    return f"- {name} (≈{fmt(tok(body))}) · {path.parent if path.name == 'SKILL.md' else path}{note}"


def skill_lines(docs_root: Path, root: str, offered: list[str]) -> list[str]:
    bases = {name: [path] for name, path in plugin_roots(root).items()} | {"": [docs_root / ".claude", CONFIG_DIR]}
    lines = [skill_line(name, skill_file(name, bases)) for name in offered]
    if not offered:
        for base in (docs_root / ".claude" / "skills", CONFIG_DIR / "skills"):
            lines += [skill_line(path.parent.name, path) for path in sorted(base.glob("*/SKILL.md"))]
    visible = {path.resolve() for path in (docs_root / ".claude" / "skills").glob("*/SKILL.md")}
    lines += [
        skill_line(path.parent.name, path, " · not in .claude/skills, so Claude Code never loads it")
        for path in sorted((docs_root / ".agents" / "skills").glob("*/SKILL.md"))
        if path.resolve() not in visible
    ]
    return lines


def write_index(path: Path, docs_root: Path, layout: Layout, root: str, offered: list[str]) -> tuple[int, int]:
    entries = load_list(docs_root, layout)
    total = sum(t for _, t in entries)
    seen: set[Path] = set()
    lines = [
        f"# Load list and index · docs tree {docs_root}",
        "",
        "## Read these whole (the ideal set is chosen from them)",
        "",
        *(f"- {rel} (≈{fmt(t)})" for rel, t in entries),
        "",
        f"Total ≈{fmt(total)} tokens in {len(entries)} files. Not listed, because Claude Code loads them at session "
        f"start and they are already in your context: {', '.join(startup_paths(docs_root)) or 'none'}.",
        "",
        "## Rules (index only; the harness injects them by paths:)",
        "",
        *rule_lines(docs_root, seen),
        "",
        f"## Skills the session was offered ({len(offered)}, from its transcript; sizes only)"
        if offered
        else "## Skills (sizes only; the transcript has no skill list)",
        "",
        *(skill_lines(docs_root, root, offered) or ["- none found"]),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return total, len(entries)


def log_dir(transcript: Path, session_id: str) -> Path:
    override = os.environ.get("CLAUDE_TRACK_DOC_READS_DIR")
    return Path(override) / session_id if override else transcript.with_suffix("") / "doc-reads"


@dataclass
class Session:
    session_id: str
    transcript: Path
    agents: list[Agent]
    root: str
    docs_root: Path
    docs_from_session: bool


def open_session(session_id: str, project_dir: str) -> Session:
    transcript = find_transcript(project_dir, session_id)
    agents = load_session(transcript)
    cwds = [r["cwd"] for r in agents[0].rows if r.get("cwd")]
    root = (cwds[0] if cwds else project_dir).split("/.claude/worktrees/")[0].rstrip("/")
    from_session = bool(cwds) and Path(cwds[0]).exists()
    return Session(
        session_id, transcript, agents, root, Path(cwds[0]) if from_session else Path(project_dir), from_session
    )


def checkout_branch(checkout: Path) -> str:
    """The branch a checkout is on, from its HEAD file, without running git."""
    git = checkout / ".git"
    try:
        if git.is_file():
            git = checkout / git.read_text(encoding="utf-8").removeprefix("gitdir:").strip()
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return "an unknown branch"
    return head.removeprefix("ref: refs/heads/") if head.startswith("ref: ") else f"a detached HEAD at {head[:9]}"


def docs_tree_line(session: Session) -> str:
    branches = ", ".join(dict.fromkeys(r["gitBranch"] for r in session.agents[0].rows if r.get("gitBranch")))
    moved = "" if session.docs_from_session else " (the session directory is gone, so the invoking project is used)"
    return (
        f"Docs tree: {session.docs_root}, on {checkout_branch(session.docs_root)} now{moved}; "
        f"the session ran on {branches or 'an unrecorded branch'}"
    )


def log_status(log: Path) -> str:
    if not log.exists():
        return f"MISSING at {log}: the context plugin was not recording this session"
    with log.open(encoding="utf-8", errors="replace") as handle:
        return f"{log} ({sum(1 for _ in handle)} lines)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir")
    parser.add_argument("invoking_session")
    parser.add_argument("session", nargs="?", help="session to audit; defaults to the invoking one")
    args = parser.parse_args()
    target = args.session or args.invoking_session
    if not UUID.match(target):
        sys.exit(f"Not a session id: {target!r}")

    session = open_session(target, args.project_dir)
    try:
        layout = load_layout(session.docs_root)
    except ValueError as error:
        sys.exit(f"Bad context plugin config: {error}")
    logs = log_dir(session.transcript, target)
    out_dir = logs / "doctor"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary, index = out_dir / "summary.md", out_dir / "index.md"
    write_summary(summary, target, session.agents, session.root, layout)
    total, count = write_index(index, session.docs_root, layout, session.root, session_skills(session.agents[0].rows))
    not_loaded = out_dir / "not-loaded.md"
    misses = write_not_loaded(not_loaded, session.transcript, session.docs_root, logs / "reads.jsonl", layout)
    offset = time.strftime("%z")
    report = [
        f"Audited session: {target}"
        + (" (the session that invoked this skill)" if target == args.invoking_session else ""),
        f"Session summary: {summary} (≈{fmt(tok(summary.read_text(encoding='utf-8')))} tokens, "
        f"{len(session.agents) - 1} subagents)",
        f"Load log: {log_status(logs / 'reads.log')}",
        f"Clocks: the load log and the summary both use this machine's local time (UTC{offset[:3]}:{offset[3:]} now)",
        f"Not loaded: {not_loaded} ({misses} items that applied to what a context worked on but never reached it)",
        f"Load list and index: {index} ({count} files to read, ≈{fmt(total)} tokens)",
        f"Layout: {layout.describe()}",
        docs_tree_line(session),
    ]
    print("\n".join(report))


if __name__ == "__main__":
    main()

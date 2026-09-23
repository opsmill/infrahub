# ruff: noqa: INP001  # standalone script, not a package
"""Draw a Mermaid diagram of the internal docs a Claude Code session read or loaded, and what led to each.

Usage:
    python3 .agents/plugins/context/scripts/context_map.py <session id | session dir | reads.jsonl> [-o out.md]
    python3 .agents/plugins/context/scripts/context_map.py [<session id>] --default-session <id> --save
    python3 .agents/plugins/context/scripts/context_map.py --list

Reads the session log written by track_reads.py. Solid arrows run from a Read to the rule or nested
CLAUDE.md it loaded, captioned with the matching `paths:` glob. Dotted arrows run to each doc from its
cause. That is a loaded file whose content was in hand before the read was issued and names the doc's
path, captioned with the section and line of the mention. Otherwise it is the prompt or subagent
brief, captioned with where the path came from.

Whether a file's content was in hand comes from the session transcript: tool calls issued in one
assistant message run in parallel, so none of them can follow from another's result. Without a
transcript, every read is attributed to its prompt or brief.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from track_reads import find_mention, glob_to_regex, load_records, preview, read_text, rule_patterns

ICONS = {"read": "📄", "rule": "📏", "claude-md": "📘", "import": "📘"}
CLASS_DEFS = {
    "header": "fill:#fffbe6,stroke:#b59f3b,color:#111",
    "read": "fill:#e8f1ff,stroke:#3b6fd8,color:#111",
    "rule": "fill:#eaf7ea,stroke:#3a9a4a,color:#111",
    "claudemd": "fill:#f3ecff,stroke:#7a4fd0,color:#111",
    "trigger": "fill:#f4f4f4,stroke:#999,color:#555",
    "skill": "fill:#fff0f6,stroke:#c0508a,color:#111",
    "startup": "fill:#f4f4f4,stroke:#999,color:#333",
}


@dataclass(frozen=True)
class Agent:
    key: str
    agent_type: str
    description: str

    brief: str
    """The prompt the subagent was started with."""

    parent: str | None
    """The subagent that started this one, or None when the main session did."""

    prompt: str | None


PROJECTS_DIR = Path.home() / ".claude" / "projects"


def session_logs() -> list[Path]:
    """Every recorded session's reads.jsonl, most recently updated first."""
    logs = list(PROJECTS_DIR.glob("*/*/doc-reads/reads.jsonl"))
    if override := os.environ.get("CLAUDE_TRACK_DOC_READS_DIR"):
        logs += Path(override).glob("*/reads.jsonl")
    return sorted(logs, key=lambda log: log.stat().st_mtime, reverse=True)


def session_id_of(log: Path) -> str:
    if log.name != "reads.jsonl":
        # A log from before logs moved into the session directory: <YYYYmmdd-HHMMSS>-<session_id>.jsonl
        return re.sub(r"^\d{8}-\d{6}-", "", log.stem)
    folder = log.parent
    return folder.parent.name if folder.name == "doc-reads" else folder.name


def mermaid_id(text: str) -> str:
    return re.sub(r"\W", "_", text)


def escape(text: str) -> str:
    return (text.replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;").replace("|", "#124;")
            .replace("`", "'"))  # fmt: skip


def heading_above(lines: list[str], line_number: int) -> str | None:
    """The nearest Markdown heading before a 1-based line, ignoring `#` lines inside code fences."""
    heading, in_fence = None, False
    for line in lines[: line_number - 1]:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and (match := re.match(r"#{1,6}\s+(.+)", line)):
            heading = match.group(1).strip()
    return heading


def load_turns(transcript: Path) -> dict[str, int]:
    """Map each tool_use_id to the position of the assistant message that issued it, per transcript file.

    Positions are only comparable within one file: the main session and each subagent have their own.
    """
    turns: dict[str, int] = {}
    for file in [transcript, *sorted((transcript.with_suffix("") / "subagents").glob("agent-*.jsonl"))]:
        positions: dict[str, int] = {}
        for row in load_records(file):
            message = row.get("message") or {}
            content = message.get("content")
            if row.get("type") != "assistant" or not isinstance(content, list):
                continue
            position = positions.setdefault(message.get("id") or row.get("uuid", ""), len(positions))
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    turns[block.get("id", "")] = position
    return turns


def transcript_of(log: Path) -> Path | None:
    """The transcript beside the session directory holding the log, else one found by session id."""
    if log.parent.name == "doc-reads":
        session_dir = log.parent.parent
        beside = session_dir.parent / f"{session_dir.name}.jsonl"
        if beside.is_file():
            return beside
    found = sorted(PROJECTS_DIR.glob(f"*/{session_id_of(log)}.jsonl"))
    return found[0] if found else None


def prompt_of(record: dict) -> str | None:
    context = record.get("context") or []
    return context[0] if context and context[0].startswith("p") else None


def clock(ts: str) -> str:
    try:
        # Python 3.10's fromisoformat does not accept a trailing "Z".
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")  # noqa: FURB162
    except ValueError:
        return ""


class Diagram:
    """Build the Mermaid flowchart for one session log, grouped by prompt and subagent."""

    def __init__(self, records: list[dict], project: Path, turns: dict[str, int] | None, all_parents: bool) -> None:
        self.records = records
        self.project = project
        self.turns = turns
        """Assistant-message position of each tool call, or None when no transcript was found."""
        self.all_parents = all_parents
        self.prompts = [r for r in records if r["kind"] == "prompt"]
        self.calls = {r["id"]: r for r in records if r["kind"] == "agent"}
        self.agent_by_call = {r["call"]: r["agent_id"] for r in records if r["kind"] == "agent-link" and r["call"]}
        self.agents = [self.agent(link) for link in records if link["kind"] == "agent-link"]
        self.startup = [r["path"] for r in records if r["kind"] == "doc" and r["via"] == "startup"]
        self.ids: dict[tuple[str | None, str], str] = {}
        """Node id per (context, path): the subagent id, None for the main session, or "startup"."""
        self.loaded_by: dict[tuple[str | None, str], dict] = {}
        """The record that first drew each (context, path)."""
        self.reads: dict[tuple[str | None, str], int] = {}
        for record in records:
            if record["kind"] == "doc" and record["via"] == "read":
                key = (record.get("agent"), record["path"])
                self.reads[key] = self.reads.get(key, 0) + 1
        self.groups: dict[str, list[str]] = {}
        self.edges: list[str] = []

    def agent(self, link: dict) -> Agent:
        call = self.calls.get(link["call"] or "", {})
        context = call.get("context", [])
        parent_call = next((c for c in reversed(context) if c in self.calls), None)
        return Agent(
            key=link["agent_id"],
            agent_type=call.get("subagent_type") or link.get("agent_type") or "agent",
            description=call.get("description", "(start not recorded)"),
            brief=call.get("prompt", ""),
            parent=self.agent_by_call.get(parent_call) if parent_call else None,
            prompt=context[0] if context else None,
        )

    def group_of(self, context: list[str]) -> str:
        """Subgraph id for the innermost prompt or subagent in a record's context."""
        for context_id in reversed(context):
            if context_id.startswith("agent:"):
                return f"A_{mermaid_id(context_id.removeprefix('agent:'))}"
            if context_id in self.agent_by_call:
                return f"A_{mermaid_id(self.agent_by_call[context_id])}"
            if context_id.startswith("p"):
                return f"P_{context_id}"
        return "P_none"

    def place(self, group: str, line: str) -> None:
        self.groups.setdefault(group, []).append(line)

    def node(self, owner: str | None, path: str, prefix: str) -> str:
        return self.ids.setdefault((owner, path), f"{prefix}{len(self.ids) + 1}")

    def render(self) -> str:
        for path in self.startup:
            self.place("startup", f'{self.node("startup", path, "st")}["{escape(path)}"]:::startup')

        docs = skills = 0
        for record in self.records:
            if record["kind"] == "skill":
                skills += 1
                label = f"🧩 {record['name']}" + (f" {preview(record['args'])}" if record["args"] else "")
                self.place(self.group_of(record["context"]), f'sk{skills}(["{escape(label)}"]):::skill')
            elif record["kind"] == "doc" and record["via"] != "startup":
                # One node per file and context; later reads only add to its count.
                if (record.get("agent"), record["path"]) in self.loaded_by:
                    continue
                docs += 1
                self.add_doc(record, docs)

        lines = ["flowchart LR", *(f"  classDef {name} {style}" for name, style in CLASS_DEFS.items())]
        if self.startup:
            lines += [
                '  subgraph startup["🚀 loaded at startup"]',
                *(f"    {n}" for n in self.groups["startup"]),
                "  end",
            ]
        lines += self.render_groups()
        lines += [f"  {edge}" for edge in self.edges]
        return "\n".join(lines)

    def add_doc(self, record: dict, number: int) -> None:
        group = self.group_of(record["context"])
        owner = record.get("agent")
        key = (owner, record["path"])
        target = self.node(owner, record["path"], "n")
        count = self.reads.get(key, 0)
        repeat = f"read {count} times" if count > 1 else None
        details = " · ".join(part for part in (record.get("lines"), clock(record["ts"]), repeat) if part)
        label = escape(f"#{number} {ICONS[record['via']]} {record['path']}")
        if details:
            label += f"<br/>{escape(details)}"
        css = {"rule": "rule", "read": "read"}.get(record["via"], "claudemd")
        self.place(group, f'{target}["{label}"]:::{css}')
        self.loaded_by[key] = record

        if record["via"] == "read":
            for source, caption in self.read_sources(record, group):
                self.edges.append(f'{source} -.->|"{escape(caption)}"| {target}')
        elif record["parents"]:
            trigger = record["parents"][0]
            if (owner, trigger) not in self.ids:
                self.place(group, f'{self.node(owner, trigger, "t")}["{escape(trigger)}"]:::trigger')
            caption = escape(self.load_caption(record, trigger))
            self.edges.append(f'{self.ids[owner, trigger]} ==>|"{caption}"| {target}')

    def load_caption(self, record: dict, trigger: str) -> str:
        if record["via"] == "import":
            return "@import"
        if record["via"] == "claude-md":
            return f"CLAUDE.md in {Path(record['path']).parent.as_posix()}/"
        patterns = rule_patterns(read_text(self.project / record["path"]))
        matched = next((p for p in patterns if glob_to_regex(p).match(trigger)), None)
        return f"matches {matched}" if matched else "path-scoped rule"

    def mention_caption(self, parent: str, child: str) -> str:
        """Where parent names child: the section heading and line, and whether it is a Markdown link."""
        text = read_text(self.project / parent)
        found = find_mention(text, Path(parent).parent, child)
        if found is None:
            return "mentions it"
        line_number, style = found
        heading = heading_above(text.splitlines(), line_number)
        parts = [
            f"§ {preview(heading)[:40]}" if heading else None,
            f"L{line_number}",
            "link" if style == "link" else None,
        ]
        return " · ".join(part for part in parts if part)

    def read_sources(self, record: dict, group: str) -> list[tuple[str, str]]:
        """Return (node id, caption) for the cause of a read.

        A loaded file is the cause only when its content was in hand before the read was issued: it came
        back in an earlier assistant message, in the same context (a subagent does not see the main
        session's), under the same prompt (after a new prompt, the prompt is what drives the next read).
        Otherwise the prompt or subagent brief is the cause, and the caption names where the path came
        from. With all_parents, every qualifying file is returned instead of the latest.
        """
        path, owner = record["path"], record.get("agent")
        in_context = [p for p in record["parents"] if (owner, p) in self.loaded_by]
        causes = [p for p in in_context if self.in_hand_before(p, record, same_prompt=True)]
        if causes:
            chosen = causes if self.all_parents else causes[-1:]
            return [(self.ids[owner, p], self.mention_caption(p, path)) for p in chosen]
        return [(f"H_{group}", self.path_caption(record, group, in_context))]

    def in_hand_before(self, parent: str, record: dict, same_prompt: bool) -> bool:
        """Whether parent's content, loaded in record's context, had come back before record's read was issued."""
        loaded = self.loaded_by.get((record.get("agent"), parent))
        if self.turns is None or loaded is None or (same_prompt and prompt_of(loaded) != prompt_of(record)):
            return False
        parent_turn = self.turns.get(loaded.get("tool_use_id") or "")
        read_turn = self.turns.get(record.get("tool_use_id") or "")
        return parent_turn is not None and read_turn is not None and parent_turn < read_turn

    def path_caption(self, record: dict, group: str, in_context: list[str]) -> str:
        """For a read the prompt or brief caused: where its path came from.

        Only a file whose content was in hand (any earlier prompt counts) or a startup file can have
        supplied the path. Without turn order, any file loaded earlier in this context is a candidate.
        """
        path = record["path"]
        agent = next((a for a in self.agents if f"A_{mermaid_id(a.key)}" == group), None)
        prompt = next((p["text"] for p in self.prompts if f"P_{p['id']}" == group), "")
        brief = agent.brief if agent else prompt
        if brief and (find_mention(brief, Path(), path) or f"/{path}" in brief):
            return "brief names it" if agent else "prompt names it"
        startup = [p for p in record["parents"] if p in self.startup]
        earlier = [p for p in in_context if self.turns is None or self.in_hand_before(p, record, same_prompt=False)]
        sources = earlier or startup
        if not sources:
            return "brief" if agent else "prompt"
        return f"path via {sources[-1]} · {self.mention_caption(sources[-1], path)}"

    def render_groups(self) -> list[str]:
        lines: list[str] = []
        children: dict[str | None, list[Agent]] = {}
        for agent in self.agents:
            children.setdefault(agent.parent, []).append(agent)

        def render_agent(agent: Agent, indent: str) -> None:
            group = f"A_{mermaid_id(agent.key)}"
            lines.extend(
                [
                    f'{indent}subgraph {group}["🤖 {escape(agent.agent_type)}"]',
                    f'{indent}  H_{group}(["{escape(preview(agent.description))}"]):::header',
                    *(f"{indent}  {node}" for node in self.groups.get(group, [])),
                ]
            )
            for child in children.get(agent.key, []):
                render_agent(child, indent + "  ")
            lines.append(f"{indent}end")

        prompts = [(p["id"], p["text"]) for p in self.prompts]
        if "P_none" in self.groups or any(a.prompt is None and a.parent is None for a in self.agents):
            prompts.append(("none", "(prompt not recorded)"))
        for prompt_id, text in prompts:
            group = f"P_{prompt_id}"
            top_agents = [a for a in children.get(None, []) if (a.prompt or "none") == prompt_id]
            nodes = self.groups.get(group, [])
            if not nodes and not top_agents:
                continue
            lines.extend(
                [
                    f'  subgraph {group}["💬 {"no prompt" if prompt_id == "none" else "prompt " + prompt_id[1:]}"]',
                    f'    H_{group}(["{escape(preview(text))}"]):::header',
                    *(f"    {node}" for node in nodes),
                ]
            )
            for agent in top_agents:
                render_agent(agent, "    ")
            lines.append("  end")
        return lines


def resolve_log(arg: str) -> Path:
    """Find a session's reads.jsonl from its path, its session directory, or its session id.

    Raises:
        SystemExit: If no log matches.

    """
    candidate = Path(arg).expanduser()
    for path in (candidate, candidate / "doc-reads" / "reads.jsonl", candidate / "reads.jsonl"):
        if path.is_file():
            return path
    for log in session_logs():
        if session_id_of(log) == arg:
            return log
    raise SystemExit(f"No doc-reads log for session {arg!r} under {PROJECTS_DIR}")


def project_of(log: Path) -> Path | None:
    """The repository a session ran in, from the header line of its readable log."""
    header = read_text(log.with_suffix(".log")).partition("\n")[0]
    match = re.match(r"# Claude session \S+ in (.+), started ", header)
    return Path(match.group(1)) if match else None


def list_logs(limit: int) -> None:
    for log in session_logs()[:limit]:
        records = load_records(log)
        prompt = next((r["text"] for r in records if r["kind"] == "prompt"), "")
        docs = sum(1 for r in records if r["kind"] == "doc" and r["via"] != "startup")
        started = re.search(r", started (\S+)", read_text(log.with_suffix(".log")).partition("\n")[0])
        print(f"{started.group(1) if started else '?':20}  {session_id_of(log)}  {docs:3} docs  {preview(prompt)[:50]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("session", nargs="?", help="session id, session directory, or reads.jsonl path")
    parser.add_argument("--default-session", help="session to draw when none is given")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    destination.add_argument("--save", action="store_true", help="also write context-map.md beside the session log")
    parser.add_argument("--format", choices=["md", "mmd"], default="md", help="Markdown with a fence, or raw Mermaid")
    parser.add_argument("--all-parents", action="store_true", help="draw every loaded file that mentions a read")
    parser.add_argument("--project", type=Path, help="repository root (default: from the session log, else cwd)")
    parser.add_argument("--transcript", type=Path, help="session transcript .jsonl (default: found by session id)")
    parser.add_argument("--list", action="store_true", help="list recorded sessions, newest first")
    args = parser.parse_args()

    if args.list:
        list_logs(limit=20)
        return
    session = args.session or args.default_session
    if not session:
        parser.error("a session id or .jsonl path is required (see --list)")

    log = resolve_log(session)
    records = load_records(log)
    project = (args.project or project_of(log) or Path.cwd()).resolve()
    transcript = args.transcript or transcript_of(log)
    turns = load_turns(transcript) if transcript and transcript.is_file() else None
    mermaid = Diagram(records=records, project=project, turns=turns, all_parents=args.all_parents).render()
    if args.format == "mmd":
        output = mermaid + "\n"
    else:
        docs = sum(1 for r in records if r["kind"] == "doc" and r["via"] != "startup")
        output = "\n".join(
            [
                f"# Docs read in session {session_id_of(log)}",
                "",
                f"{docs} docs from `{log}`. Solid arrows: a Read that loaded a rule or nested CLAUDE.md. "
                "Dotted arrows: what caused a read, either a file already in hand that names the doc, or the "
                "prompt or subagent brief, captioned with where the path came from.",
                "",
                f"Turn order from `{transcript}`."
                if turns is not None
                else "No transcript found, so every read is attributed to its prompt or brief.",
                "",
                "```mermaid",
                mermaid,
                "```",
                "",
            ]
        )
    if args.output:
        args.output.write_text(output, encoding="utf-8")
        return
    sys.stdout.write(output)
    if args.save:
        saved = log.parent / "context-map.md"
        saved.write_text(output, encoding="utf-8")
        print(f"Saved to {saved}")


if __name__ == "__main__":
    main()

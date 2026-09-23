# ruff: noqa: INP001  # standalone script, not a package
"""Draw a Mermaid diagram of the internal docs a Claude Code session read or loaded, and what led to each.

Usage:
    python3 .agents/hooks/doc_reads_diagram.py <session id | doc-reads .jsonl> [-o out.md]
    python3 .agents/hooks/doc_reads_diagram.py --list

Reads the session log written by track_dev_reads.py. Solid arrows run from a Read to the rule or nested
CLAUDE.md it loaded, captioned with the matching `paths:` glob. Dotted arrows run to a doc from the most
recently loaded file that mentions its path, captioned with the section and line of the mention, or
from the prompt or subagent brief that mentions it, or else from a startup file that does.
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from track_dev_reads import find_mention, glob_to_regex, load_records, preview, read_text, rule_patterns

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


def doc_reads_dir() -> Path:
    return Path(os.environ.get("CLAUDE_TRACK_DOC_READS_DIR") or Path.home() / ".claude" / "doc-reads")


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


def clock(ts: str) -> str:
    try:
        # Python 3.10's fromisoformat does not accept a trailing "Z".
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")  # noqa: FURB162
    except ValueError:
        return ""


class Diagram:
    """Build the Mermaid flowchart for one session log, grouped by prompt and subagent."""

    def __init__(self, records: list[dict], project: Path, all_parents: bool) -> None:
        self.records = records
        self.project = project
        self.all_parents = all_parents
        self.prompts = [r for r in records if r["kind"] == "prompt"]
        self.calls = {r["id"]: r for r in records if r["kind"] == "agent"}
        self.agent_by_call = {r["call"]: r["agent_id"] for r in records if r["kind"] == "agent-link" and r["call"]}
        self.agents = [self.agent(link) for link in records if link["kind"] == "agent-link"]
        self.startup = [r["path"] for r in records if r["kind"] == "doc" and r["via"] == "startup"]
        self.ids: dict[str, str] = {}
        self.owners: dict[str, str | None] = {}
        """The subagent (or None for the main session) whose context each drawn file entered."""
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

    def node(self, path: str, prefix: str) -> str:
        return self.ids.setdefault(path, f"{prefix}{len(self.ids) + 1}")

    def render(self) -> str:
        for path in self.startup:
            self.place("startup", f'{self.node(path, "st")}["{escape(path)}"]:::startup')

        docs = skills = 0
        for record in self.records:
            if record["kind"] == "skill":
                skills += 1
                label = f"🧩 {record['name']}" + (f" {preview(record['args'])}" if record["args"] else "")
                self.place(self.group_of(record["context"]), f'sk{skills}(["{escape(label)}"]):::skill')
            elif record["kind"] == "doc" and record["via"] != "startup":
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
        target = self.node(record["path"], "n")
        details = " · ".join(part for part in (record.get("lines"), clock(record["ts"])) if part)
        label = escape(f"#{number} {ICONS[record['via']]} {record['path']}")
        if details:
            label += f"<br/>{escape(details)}"
        css = {"rule": "rule", "read": "read"}.get(record["via"], "claudemd")
        self.place(group, f'{target}["{label}"]:::{css}')
        self.owners[record["path"]] = record.get("agent")

        if record["via"] == "read":
            for source, caption in self.read_sources(record, group):
                self.edges.append(f'{source} -.->|"{escape(caption)}"| {target}')
        elif record["parents"]:
            trigger = record["parents"][0]
            if trigger not in self.ids:
                self.place(group, f'{self.node(trigger, "t")}["{escape(trigger)}"]:::trigger')
            self.edges.append(f'{self.ids[trigger]} ==>|"{escape(self.load_caption(record, trigger))}"| {target}')

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
        """Return (node id, caption) for what most plausibly led to a read.

        Candidates, in order: a file in the same context, the prompt or brief, a startup file. A subagent
        does not see the main session's context, so only files its own context loaded count. With
        all_parents, every mentioning file in the context and every mentioning startup file is returned.
        """
        path, owner = record["path"], record.get("agent")
        files = [
            p for p in record["parents"] if p in self.ids and p not in self.startup and self.owners.get(p) == owner
        ]
        if self.all_parents:
            files = [p for p in record["parents"] if p in self.startup] + files
        if files:
            return [(self.ids[p], self.mention_caption(p, path)) for p in (files if self.all_parents else files[-1:])]
        agent = next((a for a in self.agents if f"A_{mermaid_id(a.key)}" == group), None)
        prompt = next((p["text"] for p in self.prompts if f"P_{p['id']}" == group), "")
        brief = agent.brief if agent else prompt
        if brief and (find_mention(brief, Path(), path) or f"/{path}" in brief):
            return [(f"H_{group}", "brief names it" if agent else "prompt names it")]
        startup = [p for p in record["parents"] if p in self.startup]
        return [(self.ids[p], self.mention_caption(p, path)) for p in startup[-1:]]

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
    candidate = Path(arg).expanduser()
    if candidate.is_file():
        return candidate
    logs = sorted(doc_reads_dir().glob(f"*{arg}.jsonl"))
    if not logs:
        raise SystemExit(f"No doc-reads log for session {arg!r} in {doc_reads_dir()}")
    return logs[0]


def project_of(log: Path) -> Path | None:
    """The repository a session ran in, from the header line of its readable log."""
    header = read_text(log.with_suffix(".log")).partition("\n")[0]
    match = re.match(r"# Claude session \S+ in (.+), started ", header)
    return Path(match.group(1)) if match else None


def list_logs(limit: int) -> None:
    for log in sorted(doc_reads_dir().glob("*.jsonl"), reverse=True)[:limit]:
        records = load_records(log)
        prompt = next((r["text"] for r in records if r["kind"] == "prompt"), "")
        docs = sum(1 for r in records if r["kind"] == "doc" and r["via"] != "startup")
        print(f"{log.stem}  {docs:3} docs  {preview(prompt)[:60]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("session", nargs="?", help="session id or doc-reads .jsonl path")
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    parser.add_argument("--format", choices=["md", "mmd"], default="md", help="Markdown with a fence, or raw Mermaid")
    parser.add_argument("--all-parents", action="store_true", help="draw every loaded file that mentions a read")
    parser.add_argument("--project", type=Path, help="repository root (default: from the session log, else cwd)")
    parser.add_argument("--list", action="store_true", help="list recorded sessions, newest first")
    args = parser.parse_args()

    if args.list:
        list_logs(limit=20)
        return
    if not args.session:
        parser.error("a session id or .jsonl path is required (see --list)")

    log = resolve_log(args.session)
    records = load_records(log)
    project = (args.project or project_of(log) or Path.cwd()).resolve()
    mermaid = Diagram(records=records, project=project, all_parents=args.all_parents).render()
    if args.format == "mmd":
        output = mermaid + "\n"
    else:
        docs = sum(1 for r in records if r["kind"] == "doc" and r["via"] != "startup")
        output = "\n".join(
            [
                f"# Docs read in {log.stem}",
                "",
                f"{docs} docs from `{log}`. Solid arrows: a Read that loaded a rule or nested CLAUDE.md. "
                "Dotted arrows: the file, prompt, or subagent brief that mentions the doc's path (inferred).",
                "",
                "```mermaid",
                mermaid,
                "```",
                "",
            ]
        )
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()

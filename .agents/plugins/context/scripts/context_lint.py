#!/usr/bin/env python3
"""Check that a repository's agent guidance loads once, in every harness.

Prints one line per finding. With --check it exits 1 when any finding is an error, for pre-commit and CI.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from config import load_layout, rule_patterns
from context_init import scan_skip
from doctor_inputs import GUIDANCE_SUFFIXES, fmt, tok, walk
from track_reads import MARKDOWN_LINK_TARGET, find_mention, has_claude_md, read_text

if TYPE_CHECKING:
    from collections.abc import Iterator

    from config import Layout

HARNESS_ROOTS = (".agents", ".claude")
HARNESS_DIRS = {"rules": "rule", "commands": "command", "agents": "agent"}
HARNESS_FILE = re.compile(
    r"\.(?:agents|claude)/(?:plugins/[^/]+/)?(?:(rules|commands|agents)/.+\.md|skills/[^/]+/SKILL\.md)"
)
SKILL_FOLDER = re.compile(r"\.(?:agents|claude)/(?:plugins/[^/]+/)?skills/[^/]+/")
# Codex joins the AGENTS.md files from the repository root down to its working directory and drops what
# goes past its project_doc_max_bytes default.
CODEX_CHAIN_BYTES = 32 * 1024
# A rule's whole text is injected into every context that reads a matching file, or into every session when it
# has no paths:, so it stays about a screen long.
RULE_MAX_TOKENS = 1000
IMPORT = re.compile(r"(?:^|\s)@([\w./-]+)")
CODE_SPAN = re.compile(r"`[^`]*`")
FENCE = re.compile(r"^\s*(```|~~~)")
KIB = 1024
MARKER = re.compile(r"context-lint:\s*allow")
SHIM = "@AGENTS.md\n"
HEADING = re.compile(r"#{1,6}\s")
NEGATION = re.compile(r"\b(?:no|not|never|avoid|don't|do not|without)\b", re.IGNORECASE)
CODE_TERM = re.compile(r"`([^`\n]{2,80})`")
LIST_ITEM = re.compile(r"(?:[-*+]|\d+[.)])\s")
CLAUSE_BREAK = re.compile(r"[;:()|\u2013\u2014]|\.\s")


@dataclass(frozen=True)
class Finding:
    level: str
    check: str
    where: str
    message: str

    def line(self) -> str:
        return f"{self.level.upper():7} {self.check:7} {self.where}: {self.message}"


@dataclass
class Repo:
    project: Path
    layout: Layout
    files: dict[str, str]
    """Every guidance doc, harness-loaded file and skill file, by repo-relative path, with its text."""
    harness: dict[str, str]
    """The files a harness loads on its own, by path, with their kind."""

    def docs(self) -> list[str]:
        return [rel for rel in self.files if self.layout.is_doc(rel) and rel not in self.harness]


def harness_kind(rel: str) -> str | None:
    """What a harness loads on its own: "AGENTS.md", "CLAUDE.md", "rule", "skill", "command" or "agent"."""
    name = rel.rsplit("/", 1)[-1]
    if name in {"AGENTS.md", "CLAUDE.md"}:
        return name
    match = HARNESS_FILE.fullmatch(rel)
    if not match:
        return None
    return HARNESS_DIRS[match.group(1)] if match.group(1) else "skill"


def skill_folder(rel: str) -> str | None:
    """The folder of the skill a file belongs to, such as `.agents/skills/commit/`."""
    match = SKILL_FOLDER.match(rel)
    return match.group(0) if match else None


def collect(project: Path, layout: Layout) -> Repo:
    skip = scan_skip(project) | {project / directory for directory in layout.skip_dirs}
    files, harness = {}, {}
    for path in walk(project, skip=skip):
        rel = path.relative_to(project).as_posix()
        kind = harness_kind(rel)
        if path.suffix not in GUIDANCE_SUFFIXES or not (kind or skill_folder(rel) or layout.is_doc(rel)):
            continue
        files[rel] = read_text(path)
        if kind:
            harness[rel] = kind
    return Repo(project, layout, files, harness)


def spellings(project: Path, rel: str) -> list[str]:
    """A harness file's path, and its path through the other harness folder when that is a symlink to it."""
    names = [rel]
    first, _, rest = rel.partition("/")
    if first in HARNESS_ROOTS:
        other = f"{'.claude' if first == '.agents' else '.agents'}/{rest}"
        if (project / other).is_file() and (project / other).resolve() == (project / rel).resolve():
            names.append(other)
    return names


def shim_findings(repo: Repo) -> Iterator[Finding]:
    native_off = has_claude_md(repo.project)
    for rel, kind in sorted(repo.harness.items()):
        folder = rel.rpartition("/")[0]
        beside = f"{folder}/" if folder else ""
        if kind == "AGENTS.md" and f"{beside}CLAUDE.md" not in repo.harness:
            reason = (
                "the repository has a root CLAUDE.md, which turns off Claude Code's own AGENTS.md reading"
                if native_off
                else "Claude Code reads AGENTS.md on its own only in recent versions and under some settings"
            )
            yield Finding("error", "shim", rel, f"no CLAUDE.md beside it holding @AGENTS.md, and {reason}")
        if kind == "CLAUDE.md":
            body = [line.strip() for line in repo.files[rel].splitlines() if line.strip()]
            if f"{beside}AGENTS.md" not in repo.harness:
                yield Finding(
                    "error", "shim", rel,
                    "no AGENTS.md beside it; move the guidance into AGENTS.md, which every harness reads",
                )  # fmt: skip
            elif body != ["@AGENTS.md"]:
                yield Finding(
                    "error", "shim", rel,
                    'holds more than "@AGENTS.md"; only Claude Code reads CLAUDE.md, so the rest is hidden from other harnesses',
                )  # fmt: skip


def pointer_allowed(source: str, target: str, kind: str, repo: Repo) -> bool:
    folder = skill_folder(target)
    if folder and source.startswith(folder):
        return True
    if repo.harness.get(source) == "AGENTS.md" and kind == "AGENTS.md":
        # Codex loads only the AGENTS.md files between the repository root and its working directory, so an
        # AGENTS.md naming the ones below it is how Codex sessions find them.
        above = source.rpartition("/")[0]
        return not above or target.startswith(f"{above}/")
    return False


def pointer_reason(repo: Repo, target: str, kind: str) -> str:
    if kind == "rule":
        loads = (
            "injects this rule when a file its paths match is read, so the pointer can load it twice"
            if rule_patterns(repo.files[target])
            else "loads this rule at session start, so following the pointer loads it twice"
        )
        return f"Claude Code {loads}"
    folder = target.rpartition("/")[0]
    reasons = {
        "AGENTS.md": f"Claude Code loads it on a Read below {folder}/, and Codex through the AGENTS.md above it"
        if folder
        else "every harness loads it at session start",
        "CLAUDE.md": "only Claude Code reads it, as the shim for AGENTS.md",
        "command": f"name the command, /{Path(target).stem}, and let the harness load it",
    }
    return reasons.get(kind, f"name the {kind} instead and let the harness load it")


def mention_line(lines: list[str], source: str, name: str) -> int | None:
    """The first line that points at name: a link to it, or its path when that has a folder."""
    base = Path(source).parent
    for number, line in enumerate(lines, start=1):
        if Path(name).name not in line:
            continue
        # A bare AGENTS.md or CLAUDE.md in prose names the kind of file; only a link points at the root one.
        pointed = (
            find_mention(line, base, name)
            if "/" in name
            else any(os.path.normpath(base / target) == name for target in MARKDOWN_LINK_TARGET.findall(line))
        )
        if pointed:
            return number
    return None


def pointer_findings(repo: Repo) -> Iterator[Finding]:
    for source, text in sorted(repo.files.items()):
        if repo.harness.get(source) == "CLAUDE.md" or repo.layout.allows_references(source):
            continue
        lines = text.splitlines()
        for target, kind in sorted(repo.harness.items()):
            if target == source or pointer_allowed(source, target, kind, repo):
                continue
            for name in spellings(repo.project, target):
                if Path(name).name in text and (number := mention_line(lines, source, name)):
                    reason = pointer_reason(repo, target, kind)
                    yield Finding("error", "pointer", f"{source}:{number}", f"names {name}: {reason}")
                    break


def import_findings(repo: Repo) -> Iterator[Finding]:
    for source, text in sorted(repo.files.items()):
        if repo.harness.get(source) == "CLAUDE.md":
            continue
        fenced = False
        lines = text.splitlines()
        for number, line in enumerate(lines, start=1):
            if FENCE.match(line):
                fenced = not fenced
                continue
            for target in [] if fenced else IMPORT.findall(CODE_SPAN.sub("", line)):
                if (repo.project / Path(source).parent / target).is_file():
                    yield Finding(
                        "error", "import", f"{source}:{number}",
                        f"@{target} is an import only Claude Code expands; other harnesses read the text, so link it instead",
                    )  # fmt: skip


def marker_findings(repo: Repo) -> Iterator[Finding]:
    for source, text in sorted(repo.files.items()):
        for number, line in enumerate(text.splitlines(), start=1):
            if MARKER.search(line):
                yield Finding(
                    "error", "marker", f"{source}:{number}",
                    "the lint ignores inline allow markers; name the file without its path, or list this file "
                    "under lint_allow in the config",
                )  # fmt: skip


def chain_sizes(repo: Repo) -> dict[str, int]:
    """The bytes Codex joins for a session in each folder that has an AGENTS.md, from the root down."""
    sizes = {
        rel.rpartition("/")[0]: len((repo.project / rel).read_bytes())
        for rel, kind in repo.harness.items()
        if kind == "AGENTS.md"
    }
    return {
        folder: sum(
            size for above, size in sizes.items() if not above or folder == above or folder.startswith(f"{above}/")
        )
        for folder in sizes
    }


def size_findings(repo: Repo) -> Iterator[Finding]:
    for folder, total in sorted(chain_sizes(repo).items()):
        if total > CODEX_CHAIN_BYTES:
            where = f"{folder}/AGENTS.md" if folder else "AGENTS.md"
            yield Finding(
                "error", "size", where,
                f"the AGENTS.md files from the root down to here add up to {total / KIB:.1f} KiB, and Codex drops "
                f"what goes past its {CODEX_CHAIN_BYTES // KIB} KiB default",
            )  # fmt: skip


def rule_size_findings(repo: Repo) -> Iterator[Finding]:
    for rule in sorted(rel for rel, kind in repo.harness.items() if kind == "rule"):
        tokens = tok(repo.files[rule])
        if tokens > RULE_MAX_TOKENS:
            where = "every context that reads a matching file" if rule_patterns(repo.files[rule]) else "every session"
            yield Finding(
                "error", "rule", rule,
                f"is \u2248{fmt(tokens)} tokens, and Claude Code injects all of it into {where}; keep a rule under "
                f"\u2248{fmt(RULE_MAX_TOKENS)} tokens",
            )  # fmt: skip


def references(repo: Repo, targets: list[str]) -> dict[str, set[str]]:
    edges = defaultdict(set)
    for source, text in repo.files.items():
        for target in targets:
            if target != source and Path(target).name in text and find_mention(text, Path(source).parent, target):
                edges[source].add(target)
    return edges


def link_hint(doc: str, docs: list[str], edges: dict[str, set[str]], reachable: set[str]) -> str:
    """Where to link an orphan: the reachable file that names the most docs in its folder."""
    folder = doc.rpartition("/")[0]
    siblings = {other for other in docs if other != doc and other.rpartition("/")[0] == folder}
    votes = Counter(source for source, targets in edges.items() if source in reachable for _ in targets & siblings)
    if not votes:
        return ""
    source, _ = votes.most_common(1)[0]
    return f"; its neighbours in {folder}/ are named from {source}, so link it there"


def orphan_findings(repo: Repo) -> Iterator[Finding]:
    docs = repo.docs()
    edges = references(repo, docs)
    roots = {rel for rel in repo.files if rel in repo.harness or skill_folder(rel)}
    reached: set[str] = set()
    frontier = list(roots)
    while frontier:
        for target in edges.get(frontier.pop(), ()):
            if target not in reached:
                reached.add(target)
                frontier.append(target)
    for doc in sorted(set(docs) - reached):
        sources = sorted(source for source, targets in edges.items() if doc in targets)
        if sources:
            message = f"only {', '.join(sources[:3])} name it, and no file a harness loads leads there"
        else:
            message = "nothing names it, so no session will load it"
        yield Finding("warning", "orphan", doc, message + link_hint(doc, docs, edges, roots | reached))


def rule_docs(repo: Repo) -> dict[str, list[str]]:
    """Every rule, with the guidance docs it names."""
    edges = references(repo, repo.docs())
    return {
        rule: sorted(edges.get(rule, ())) for rule in sorted(r for r, kind in repo.harness.items() if kind == "rule")
    }


def paragraphs(text: str) -> Iterator[list[tuple[int, str]]]:
    """Runs of prose outside code fences, split at blank lines, list items, headings, quotes and table rows."""
    run: list[tuple[int, str]] = []
    fenced = False
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if FENCE.match(raw):
            fenced = not fenced
            line = ""
        elif fenced:
            continue
        if run and (not line or LIST_ITEM.match(line) or line.startswith(("#", "|", ">"))):
            yield run
            run = []
        if line:
            run.append((number, line))
    if run:
        yield run


def stances(text: str) -> dict[str, dict[bool, int]]:
    """Each code term the prose names, with the first line naming it after a negation in its clause, and without."""
    found: dict[str, dict[bool, int]] = defaultdict(dict)
    for run in paragraphs(text):
        joined, starts = "", []
        for number, line in run:
            starts.append((len(joined), number))
            joined += line + " "
        # Blank out code spans so their commas and words neither split clauses nor read as negations.
        masked = CODE_SPAN.sub(lambda span: "`" + "x" * (len(span.group()) - 2) + "`", joined)
        for match in CODE_TERM.finditer(joined):
            before = masked[: match.start()]
            clause = before[max((brk.end() for brk in CLAUSE_BREAK.finditer(before)), default=0) :]
            number = next(line_number for offset, line_number in reversed(starts) if offset <= match.start())
            found[match.group(1)].setdefault(bool(NEGATION.search(clause)), number)
    return found


def conflict_findings(repo: Repo) -> Iterator[Finding]:
    """A code term a rule recommends and the doc it names advises against, such as a tool the doc rules out."""
    for rule, docs in rule_docs(repo).items():
        ours = stances(repo.files[rule])
        for doc in docs:
            theirs = stances(repo.files[doc])
            for term in sorted(ours.keys() & theirs.keys()):
                # A doc explaining why something is bad often names it without a negation, so only this
                # direction is reliable: the rule only ever recommends the term, the doc only ever rules it out.
                if set(ours[term]) == {False} and set(theirs[term]) == {True}:
                    yield Finding(
                        "warning", "conflict", f"{rule}:{ours[term][False]}",
                        f"recommends `{term}`, but {doc}:{theirs[term][True]} advises against it; make them agree",
                    )  # fmt: skip


def fix_shims(repo: Repo) -> list[str]:
    """Create each missing CLAUDE.md shim, and trim a shim that holds only headings besides the import."""
    fixed = []
    for rel, kind in sorted(repo.harness.items()):
        folder = rel.rpartition("/")[0]
        beside = f"{folder}/" if folder else ""
        if kind == "AGENTS.md" and f"{beside}CLAUDE.md" not in repo.harness:
            (repo.project / f"{beside}CLAUDE.md").write_text(SHIM, encoding="utf-8")
            fixed.append(f"FIXED   shim    {beside}CLAUDE.md: created, holding @AGENTS.md")
        elif kind == "CLAUDE.md" and f"{beside}AGENTS.md" in repo.harness:
            body = [line.strip() for line in repo.files[rel].splitlines() if line.strip()]
            extra = [line for line in body if line != SHIM.strip()]
            if SHIM.strip() in body and extra and all(HEADING.match(line) for line in extra):
                (repo.project / rel).write_text(SHIM, encoding="utf-8")
                fixed.append(f"FIXED   shim    {rel}: trimmed to @AGENTS.md")
    return fixed


def summary(repo: Repo, findings: list[Finding]) -> list[str]:
    errors = sum(finding.level == "error" for finding in findings)
    sizes = chain_sizes(repo)
    largest = max(sizes, key=lambda folder: sizes[folder], default=None)
    chain = (
        f"largest AGENTS.md chain: {largest or 'the root'} at {sizes[largest] / KIB:.1f} KiB of Codex's "
        f"{CODEX_CHAIN_BYTES // KIB} KiB"
        if largest is not None
        else "no AGENTS.md"
    )
    allow = (
        ["A pointer that only mentions a file: name the file without its path, or list its file under lint_allow"]
        if any(finding.check == "pointer" for finding in findings)
        else []
    )
    return [
        f"{errors} errors, {len(findings) - errors} warnings in {len(repo.files)} files · {chain}",
        *allow,
        f"Repository: {repo.project}",
        f"Layout: {repo.layout.describe()}",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("project", type=Path)
    parser.add_argument("--check", action="store_true", help="exit 1 when any finding is an error")
    parser.add_argument("--fix", action="store_true", help="create missing CLAUDE.md shims and trim padded ones")
    args = parser.parse_args()
    project = args.project.resolve()
    try:
        layout = load_layout(project)
    except ValueError as error:
        sys.exit(f"Bad context plugin config: {error}")
    repo = collect(project, layout)
    fixed = fix_shims(repo) if args.fix else []
    if fixed:
        repo = collect(project, layout)
    findings = [
        *shim_findings(repo),
        *pointer_findings(repo),
        *import_findings(repo),
        *marker_findings(repo),
        *size_findings(repo),
        *rule_size_findings(repo),
        *orphan_findings(repo),
        *conflict_findings(repo),
    ]
    findings.sort(key=lambda finding: finding.level != "error")
    print("\n".join([*fixed, *(finding.line() for finding in findings), *summary(repo, findings)]))
    if args.check and any(finding.level == "error" for finding in findings):
        sys.exit(1)


if __name__ == "__main__":
    main()

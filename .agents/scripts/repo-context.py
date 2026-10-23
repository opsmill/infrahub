#!/usr/bin/env python3
"""Compute which repository instructions apply to a set of files: the matching `.agents/rules/` files and nearest `AGENTS.md`.

Modes: the default prints the review manifest for the current branch; `--check-index` fails when a `dev/` article has
no `AGENTS.md` entry; `--hook` is a Claude Code hook that adds the instructions Claude Code does not load on its own;
`--hooks-status` fails unless this checkout's hooks have run in the current session.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess  # noqa: S404
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Area = Literal["dev-specs", "dev-docs", "changelog", "frontend", "backend-tests", "backend", "other"]

BASE_CANDIDATES = ("stable", "develop")
# Exit code 1 already means "nothing to review".
EXIT_GIT_FAILED = 2
# Claude Code replaces hook context longer than about 10,000 characters with a short preview and a file path.
HOOK_BUDGET = 9_500
ROOT_MAP_PRIORITY = ("# Infrahub", "## Coding Standards", "## Boundaries", "## Navigation", "## Component Maps")
RULES_DIR = Path(".agents/rules")
# Rules come from the checkout this script lives in, so a checkout without the tooling can be reviewed in place.
TOOLING_ROOT = Path(__file__).resolve().parents[2]
DOC_DIRS = (Path("dev/knowledge"), Path("dev/guidelines"), Path("dev/guides"))
SOURCE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
# The first matching prefix wins, so a subfolder's area comes before its parent's.
AREAS: tuple[tuple[Area, tuple[str, ...]], ...] = (
    ("dev-specs", ("dev/specs/",)),
    ("dev-docs", ("dev/",)),
    ("changelog", ("changelog/",)),
    ("frontend", ("frontend/",)),
    ("backend-tests", ("backend/tests/", "python_testcontainers/tests/")),
    ("backend", ("backend/", "python_testcontainers/", "tasks/")),
)


@dataclass
class Rule:
    path: str
    chars: int
    globs: list[str]
    matched: dict[str, str] = field(default_factory=dict)


@dataclass
class ChangeSet:
    files: list[str]
    deleted: list[str]
    uncommitted_only: list[str]
    excluded: list[str]
    skipped_submodules: list[str]


@dataclass
class Article:
    path: str
    chars: int
    title: str
    headings: list[str]


def git(*args: str) -> str:
    executable = shutil.which("git")
    if executable is None:
        print("git is not installed", file=sys.stderr)
        raise SystemExit(EXIT_GIT_FAILED)
    return subprocess.run([executable, *args], capture_output=True, text=True, check=True).stdout  # noqa: S603


def pr_base() -> str:
    executable = shutil.which("gh")
    if executable is None:
        return ""
    try:
        result = subprocess.run(  # noqa: S603
            [executable, "pr", "view", "--json", "baseRefName", "-q", ".baseRefName"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def resolve_base(requested: str) -> tuple[str, str]:
    if requested:
        return requested, "argument"
    if base := pr_base():
        return base, "open PR"
    ahead = {name: int(git("rev-list", "--count", f"origin/{name}..HEAD")) for name in BASE_CANDIDATES}
    return min(ahead, key=lambda name: ahead[name]), f"closest of stable/develop (commits ahead: {ahead})"


def submodule_paths() -> set[str]:
    entries = git("ls-files", "-s").splitlines()
    return {line.split("\t", 1)[1] for line in entries if line.startswith("160000 ")}


def uncommitted_files() -> list[str]:
    entries = git("status", "--porcelain", "-z", "--no-renames", "--untracked-files=all").split("\0")
    return [entry[3:] for entry in entries if entry]


def changed_files(base: str, *, include_uncommitted: bool, excludes: list[str]) -> ChangeSet:
    git("fetch", "--quiet", "origin", base)
    committed = set(git("diff", "--name-only", "-z", "--no-renames", f"origin/{base}...HEAD").split("\0")) - {""}
    uncommitted = set(uncommitted_files())
    submodules = submodule_paths()
    candidates = committed | uncommitted if include_uncommitted else committed
    patterns = [glob_to_regex(pattern) for pattern in excludes]
    excluded = {path for path in candidates if any(pattern.match(path) for pattern in patterns)}
    deleted = {path for path in candidates - excluded - submodules if not os.path.lexists(path)}
    return ChangeSet(
        files=sorted(candidates - excluded - submodules - deleted),
        deleted=sorted(deleted),
        uncommitted_only=sorted(uncommitted - committed - submodules - deleted),
        excluded=sorted(excluded),
        skipped_submodules=sorted(submodules & (committed | uncommitted)),
    )


def is_source(path: str) -> bool:
    return path.endswith(SOURCE_SUFFIXES)


def area_of(path: str) -> Area:
    for name, prefixes in AREAS:
        if path.startswith(prefixes):
            return name
    return "other"


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    out = ""
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile(f"^{out}$")


def frontmatter_globs(text: str) -> list[str]:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return []
    return re.findall(r"^\s*-\s*[\"']?([^\"'\n]+)[\"']?\s*$", match.group(1), re.MULTILINE)


def load_rules(files: list[str]) -> list[Rule]:
    rules = []
    for rule_path in sorted((TOOLING_ROOT / RULES_DIR).glob("*.md")):
        text = rule_path.read_text(encoding="utf-8")
        rule = Rule(path=str(rule_path.relative_to(TOOLING_ROOT)), chars=len(text), globs=frontmatter_globs(text))
        patterns = [(pattern, glob_to_regex(pattern)) for pattern in rule.globs]
        for path in files:
            if not rule.globs:
                if is_source(path):
                    rule.matched.setdefault("(no paths: applies to every source file)", path)
                continue
            for pattern, regex in patterns:
                if regex.match(path):
                    rule.matched.setdefault(pattern, path)
        if rule.matched:
            rules.append(rule)
    return rules


def nearest_maps(files: list[str]) -> dict[str, list[str]]:
    maps = sorted(git("ls-files", "*AGENTS.md").splitlines(), key=str.__len__)
    found: dict[str, list[str]] = {"AGENTS.md": list(files)}
    for path in files:
        owners = [m for m in maps if path.startswith(str(Path(m).parent) + "/")]
        if owners:
            found.setdefault(max(owners, key=str.__len__), []).append(path)
    return found


def table_of_contents() -> list[Article]:
    articles = []
    for directory in DOC_DIRS:
        for doc in sorted(directory.rglob("*.md")):
            text = doc.read_text(encoding="utf-8")
            titles = re.findall(r"^# (.+)$", text, re.MULTILINE)
            headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
            articles.append(
                Article(path=str(doc), chars=len(text), title=titles[0] if titles else doc.stem, headings=headings)
            )
    return articles


def print_markdown(context: dict) -> None:
    print(f"# Review context\n\nReviewed checkout: {context['repo']}")
    if context["rules_root"] != context["repo"]:
        print(f"Rules from: {context['rules_root']}")
    print(f"Base: origin/{context['base']} ({context['base_source']})")
    scope = "committed and uncommitted" if context["include_uncommitted"] else "committed only"
    print(f"Scope: {scope}; excluded: {', '.join(context['exclude']) or 'nothing'}\n")
    print(f"## Changed files ({len(context['files'])})\n")
    for area, paths in context["areas"].items():
        print(f"- {area}: {len(paths)}")
        for path in paths:
            print(f"  - {path}")
    if context["uncommitted_only"]:
        print(f"\n## Uncommitted files outside the committed range ({len(context['uncommitted_only'])})\n")
        for path in context["uncommitted_only"]:
            print(f"- {path}")
    if context["deleted"]:
        print(f"\n## Deleted files ({len(context['deleted'])})\n")
        for path in context["deleted"]:
            print(f"- {path}")
    if context["excluded"]:
        print(f"\nExcluded from the review: {', '.join(context['excluded'])}")
    if context["skipped_submodules"]:
        print(f"\nSubmodule pointers not reviewed here: {', '.join(context['skipped_submodules'])}")
    print(f"\n## Rules that apply ({len(context['rules'])})\n")
    for rule in context["rules"]:
        reasons = "; ".join(f"`{glob}` matches {path}" for glob, path in rule["matched"].items())
        absent = "" if rule["on_base"] else f" — not on origin/{context['base']}: findings citing it are advisory"
        print(f"- {rule['path']} ({rule['chars']} chars) — {reasons}{absent}")
    print("\n## Rules by area\n")
    for area, rule_paths in context["area_rules"].items():
        print(f"- {area}: {', '.join(rule_paths) or 'no rule matches'}")
    print("\n## Area maps (nearest AGENTS.md)\n")
    for agents_map, paths in context["maps"].items():
        print(f"- {agents_map} — {len(paths)} changed files")


def unindexed_articles() -> list[str]:
    maps_text = "\n".join(Path(m).read_text(encoding="utf-8") for m in git("ls-files", "*AGENTS.md").splitlines())
    return [article.path for article in table_of_contents() if article.path not in maps_text]


def check_index() -> int:
    missing = unindexed_articles()
    if not missing:
        print("Every article in dev/knowledge, dev/guidelines and dev/guides is listed in an AGENTS.md file.")
        return 0
    print("These articles are not listed in any AGENTS.md file, so agents cannot find them:", file=sys.stderr)
    for path in missing:
        print(f"  - {path}", file=sys.stderr)
    print("Add each one, with when to load it, to the AGENTS.md of its area.", file=sys.stderr)
    return 1


def nearest_area_map(path: str, maps: list[str]) -> str | None:
    owners = [m for m in maps if m != "AGENTS.md" and path.startswith(str(Path(m).parent) + "/")]
    return max(owners, key=str.__len__) if owners else None


def tracked_files_under(path: str) -> list[str]:
    return git("ls-files", "--", path).splitlines()


def paths_from_tool(tool_name: str, tool_input: dict, cwd: Path, root: Path) -> list[str]:
    if tool_name == "Bash":
        try:
            candidates = shlex.split(tool_input.get("command", ""))
        except ValueError:
            candidates = tool_input.get("command", "").split()
    elif tool_name == "Glob":
        candidates = [tool_input.get("path") or "", tool_input.get("pattern") or ""]
    else:
        candidates = [tool_input.get("path") or "", tool_input.get("glob") or ""]
    found = []
    for raw in candidates:
        static = re.split(r"[*?\[{]", raw, maxsplit=1)[0]
        if not static or static.startswith("-"):
            continue
        resolved = (cwd / static).resolve()
        # A token longer than a file name can be returns False here instead of raising.
        if not os.path.exists(resolved):  # noqa: PTH110
            resolved = resolved.parent
        try:
            relative = resolved.relative_to(root)
        except ValueError:
            continue
        if str(relative) != "." and os.path.exists(resolved):  # noqa: PTH110
            found.append(str(relative))
    return found


def instructions_for(paths: list[str]) -> dict[str, str]:
    maps = git("ls-files", "*AGENTS.md").splitlines()
    files: list[str] = []
    for path in paths:
        files.extend([path] if Path(path).is_file() else tracked_files_under(path))
    reasons: dict[str, str] = {}
    for path in files:
        if (area_map := nearest_area_map(path, maps)) is not None:
            reasons.setdefault(area_map, path)
    for rule in load_rules(files):
        if rule.globs:
            reasons.setdefault(rule.path, next(iter(rule.matched.values())))
    return reasons


def emit(event: str, text: str) -> None:
    json.dump({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}, sys.stdout)


def root_map_digest(budget: int) -> str:
    parts = re.split(r"(?m)^(?=## )", Path("AGENTS.md").read_text(encoding="utf-8"))
    ranked = sorted(parts, key=lambda part: next((i for i, h in enumerate(ROOT_MAP_PRIORITY) if h in part[:60]), 99))
    kept, skipped, size = [], [], 0
    for part in ranked:
        if size + len(part) <= budget:
            kept.append(part)
            size += len(part)
        else:
            skipped.append(part.splitlines()[0].lstrip("# "))
    text = "".join(part for part in parts if part in kept)
    if skipped:
        text += f"\n\nNot shown here, read AGENTS.md for: {', '.join(skipped)}."
    return text


def hook_marker(session_id: str) -> Path:
    return Path(tempfile.gettempdir()) / f"claude-hooks-{session_id}.txt"


def hooks_status() -> int:
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    toplevel = Path(git("rev-parse", "--show-toplevel").strip()).resolve()
    marker = hook_marker(session_id)
    if not session_id or not marker.exists():
        print("inactive: no context hook has run in this session")
        return 1
    project = Path(marker.read_text(encoding="utf-8").strip()).resolve()
    if project != toplevel:
        print(f"inactive: the hooks that ran belong to {project}, not {toplevel}")
        return 1
    print(f"active: the context hooks of {toplevel} run in this session")
    return 0


def run_hook() -> int:
    # Exit code 2 would block every tool call, so a machine without git gets no context instead.
    if shutil.which("git") is None:
        return 0
    data = json.load(sys.stdin)
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data["cwd"]).resolve()
    os.chdir(root)
    hook_marker(data["session_id"]).write_text(str(root), encoding="utf-8")
    event = data["hook_event_name"]

    if event == "SubagentStart":
        if data.get("agent_type") == "general-purpose":
            return 0
        header = "Repository instructions from the root AGENTS.md, which this agent type does not load:\n\n"
        emit(event, header + root_map_digest(HOOK_BUDGET - len(header)))
        return 0

    paths = paths_from_tool(data.get("tool_name", ""), data.get("tool_input", {}), Path(data["cwd"]), root)
    if not paths:
        return 0
    state = Path(tempfile.gettempdir()) / f"claude-context-{data['session_id']}-{data.get('agent_id', 'main')}.json"
    loaded = set(json.loads(state.read_text())) if state.exists() else set()
    new = {doc: path for doc, path in instructions_for(paths).items() if doc not in loaded}
    if not new:
        return 0

    header = f"Repository instructions for the files this {data['tool_name']} call touched:"
    sections, too_long, crowded_out, size = [], [], [], len(header)
    for doc, path in sorted(new.items(), key=lambda item: not item[0].startswith(str(RULES_DIR))):
        section = f"\n\n## {doc} (applies to {path})\n\n{Path(doc).read_text(encoding='utf-8')}"
        if size + len(section) <= HOOK_BUDGET:
            sections.append(section)
            size += len(section)
        elif len(header) + len(section) > HOOK_BUDGET:
            too_long.append(doc)
        else:
            crowded_out.append(doc)
    # A document crowded out by others stays unloaded, so a later call includes it.
    state.write_text(json.dumps(sorted(loaded | (set(new) - set(crowded_out)))))
    text = header + "".join(sections)
    if too_long:
        text += "\n\nAlso applies, too long to include here. Read it before changing these files: " + ", ".join(
            too_long
        )
    if crowded_out:
        text += "\n\nAlso applies, included on a later call: " + ", ".join(crowded_out)
    emit(event, text)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base", default="", help="Base branch; defaults to the open PR's base, then the closest of stable/develop"
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    parser.add_argument(
        "--check-index", action="store_true", help="Fail when an article is not listed in any AGENTS.md"
    )
    parser.add_argument("--hook", action="store_true", help="Run as a Claude Code SubagentStart or PostToolUse hook")
    parser.add_argument(
        "--hooks-status", action="store_true", help="Fail unless this checkout's context hooks ran in this session"
    )
    parser.add_argument(
        "--repo", default=".", help="Checkout to review; rules still come from the checkout this script is in"
    )
    parser.add_argument("--committed", action="store_true", help="Leave uncommitted files out of the change")
    parser.add_argument(
        "--exclude", action="append", default=[], metavar="GLOB", help="Leave matching paths out (repeatable)"
    )
    args = parser.parse_args()
    if not Path(args.repo).is_dir():
        parser.error(f"--repo {args.repo} is not a directory")
    if args.hook:
        return run_hook()
    if args.hooks_status:
        return hooks_status()
    if args.check_index:
        return check_index()

    try:
        return review_manifest(args)
    except subprocess.CalledProcessError as error:
        print(f"git {' '.join(error.cmd[1:])} failed: {error.stderr.strip()}", file=sys.stderr)
        return EXIT_GIT_FAILED


def on_base(base: str, path: str) -> bool:
    try:
        git("cat-file", "-e", f"origin/{base}:{path}")
    except subprocess.CalledProcessError:
        return False
    return True


def review_manifest(args: argparse.Namespace) -> int:
    os.chdir(args.repo)
    os.chdir(git("rev-parse", "--show-toplevel").strip())
    base, base_source = resolve_base(args.base)
    change = changed_files(base, include_uncommitted=not args.committed, excludes=args.exclude)
    files = change.files
    # A deletion still brings in the rules and AGENTS.md of its area, for references left behind.
    touched = files + change.deleted
    areas: dict[Area, list[str]] = {}
    for path in files:
        areas.setdefault(area_of(path), []).append(path)
    context = {
        "base": base,
        "base_source": base_source,
        "repo": str(Path.cwd()),
        "rules_root": str(TOOLING_ROOT),
        "include_uncommitted": not args.committed,
        "exclude": args.exclude,
        "files": files,
        "deleted": change.deleted,
        "uncommitted_only": change.uncommitted_only,
        "excluded": change.excluded,
        "skipped_submodules": change.skipped_submodules,
        "areas": areas,
        "rules": [asdict(rule) | {"on_base": on_base(base, rule.path)} for rule in load_rules(touched)],
        "area_rules": {area: [rule.path for rule in load_rules(paths)] for area, paths in areas.items()},
        "maps": nearest_maps(touched),
    }
    if args.json:
        json.dump(context, sys.stdout, indent=2)
    else:
        print_markdown(context)
    return 0 if files or change.deleted else 1


if __name__ == "__main__":
    sys.exit(main())

# ruff: noqa: INP001  # standalone script, not a package
"""Set up the context plugin for a repository: scan where its guidance lives, write the config, check it.

Usage:
    python3 context_init.py scan <project>
    python3 context_init.py write <project> --location {both,claude,agents} --docs GLOB [--docs GLOB ...]
        [--also-logged GLOB ...] [--working-files GLOB ...] [--skip-dirs DIR ...] [--force]
    python3 context_init.py check <project>
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from config import DEFAULTS, KEYS, LOCAL_FILES, PROJECT_FILES, find_config, load_layout, matches
from doctor_inputs import BYTES_PER_TOKEN, fmt, load_list, startup_paths, walk
from track_reads import claude_md_imports, has_claude_md, instruction_files, reads_agents_md

LOCATIONS = {"both": ".agents/context.md", "agents": ".agents/context.md", "claude": ".claude/context.md"}
WORKING_NAMES = {"specs", ".specify", "plans", "rfcs"}
VENDORED_NAMES = {"vendor", "vendored", "third_party", "external"}
TOP_FOLDERS = 15
BODY = """# Context plugin layout

Where this repository keeps its agent guidance, for the `context` Claude Code plugin. Written by
`/context:init`; edit it by hand or run `/context:init` again.

- `docs`: guidance. Every Read of it is logged, and `/context:doctor` reads all of it.
- `also_logged`: Reads are logged too, but the doctor does not read these.
- `working_files`: material a session works on, such as specs. Logged, never judged as guidance.
- `skip_dirs`: never scanned, such as submodules.

A `context.local.md` next to this file, kept out of git, replaces whole keys for one person.
"""


def submodules(project: Path) -> list[str]:
    text = (project / ".gitmodules").read_text(encoding="utf-8") if (project / ".gitmodules").is_file() else ""
    return [line.split("=", 1)[1].strip() for line in text.splitlines() if line.strip().startswith("path")]


def scan_skip(project: Path) -> set[Path]:
    return {project / path for path in submodules(project)} | {project / ".claude" / "worktrees"}


def config_lines(project: Path) -> list[str]:
    lines = []
    for name in (*PROJECT_FILES, *LOCAL_FILES):
        path = project / name
        if path.is_symlink():
            lines.append(f"- {name}: symlink to {path.readlink()}")
        elif path.is_file():
            lines.append(f"- {name}: file")
    try:
        layout = f"- Effective layout: {load_layout(project).describe()}"
    except ValueError as error:
        layout = f"- Config error: {error}"
    return ["## Config", "", *(lines or ["- No context.md in .agents/ or .claude/ yet"]), layout]


def folder_lines(project: Path) -> list[str]:
    present = [name for name in (".agents", ".claude") if (project / name).is_dir()]
    lines = ["## .agents/ and .claude/", "", f"- Present: {', '.join(present) or 'neither'}"]
    for kind in ("rules", "skills", "commands"):
        claude, agents = project / ".claude" / kind, project / ".agents" / kind
        if claude.is_symlink():
            state = f".claude/{kind} is a symlink to {claude.readlink()}"
        elif claude.is_dir():
            state = f".claude/{kind} is a folder"
        else:
            state = f"no .claude/{kind}"
        if agents.is_dir() and not (claude.exists() and claude.resolve() == agents.resolve()):
            state += f"; .agents/{kind} is not linked from .claude/{kind}, so Claude Code never reads it"
        lines.append(f"- {kind}: {state}")
    return lines


def instruction_lines(project: Path, instruction_paths: list[str]) -> list[str]:
    mode = instruction_files()
    agents_md = reads_agents_md(project, mode)
    lines = [
        "## Instruction files",
        "",
        f"- Your instruction-files setting is {mode}, so Claude Code "
        + ("reads" if agents_md else "does not read")
        + " this repository's AGENTS.md files on its own",
        f"- Loaded at session start: {', '.join(startup_paths(project)) or 'nothing'}",
    ]
    for rel in instruction_paths:
        directory = Path(rel).parent
        if Path(rel).name == "CLAUDE.md":
            lines.append(f"- {rel}: loads when a file below it is read")
            continue
        beside = (directory / "CLAUDE.md").as_posix()
        imported = (project / beside).is_file() and any(
            path == rel for path, _ in claude_md_imports(project, beside, {beside})
        )
        if imported:
            how = f"loads through {beside}"
        elif agents_md and (mode == "claude-md-and-agents-md" or not has_claude_md(project / directory)):
            how = "loads when a file below it is read"
        else:
            how = "never loads on its own; only an explicit Read or an import picks it up"
        lines.append(f"- {rel}: {how}")
    return lines


def scan(project: Path) -> None:
    folder_bytes: Counter[str] = Counter()
    folder_files: Counter[str] = Counter()
    working: Counter[str] = Counter()
    instruction_paths = []
    for path in walk(project, skip=scan_skip(project)):
        parts = path.relative_to(project).parts
        rel = "/".join(parts)
        if len(parts) > 1 and path.name in {"AGENTS.md", "CLAUDE.md"}:
            instruction_paths.append(rel)
        if hits := [i for i, part in enumerate(parts[:-1]) if part in WORKING_NAMES]:
            working["/".join(parts[: hits[0] + 1])] += 1
        if path.suffix in {".md", ".mdx"} and len(parts) > 1:
            size = path.stat().st_size
            for depth in (1, 2):
                if len(parts) > depth:
                    folder = "/".join(parts[:depth])
                    folder_bytes[folder] += size
                    folder_files[folder] += 1
    vendored = sorted(p.name for p in project.iterdir() if p.is_dir() and p.name in VENDORED_NAMES)
    lines = [
        f"# Context plugin scan · {project}",
        "",
        *config_lines(project),
        "",
        *folder_lines(project),
        "",
        *instruction_lines(project, instruction_paths),
        "",
        "## Folders holding Markdown, largest first",
        "",
        *(
            f"- {folder}/ · {folder_files[folder]} files · ≈{fmt(size // BYTES_PER_TOKEN)} tokens"
            for folder, size in folder_bytes.most_common(TOP_FOLDERS)
        ),
        "",
        "## Working-material candidates",
        "",
        *([f"- {folder}/ · {count} files" for folder, count in sorted(working.items())] or ["- none found"]),
        "",
        "## Skip candidates",
        "",
        *([f"- {path}/ · git submodule" for path in submodules(project)] + [f"- {name}/" for name in vendored]
          or ["- none found"]),
    ]  # fmt: skip
    print("\n".join(lines))


def check(project: Path) -> None:
    try:
        layout = load_layout(project)
    except ValueError as error:
        sys.exit(f"Config error: {error}")
    entries = load_list(project, layout)
    biggest = sorted(entries, key=lambda entry: -entry[1])[:5]
    working = sum(
        1
        for path in walk(project, skip=scan_skip(project))
        if matches(path.relative_to(project).as_posix(), layout.working_files)
    )
    lines = [
        f"# Context plugin check · {project}",
        "",
        f"- Layout: {layout.describe()}",
        f"- The tracker logs Reads of: {', '.join(layout.docs + layout.also_logged + layout.working_files)}",
        f"- Loaded at session start under your {instruction_files()} setting: "
        f"{', '.join(startup_paths(project)) or 'nothing'}",
        f"- /context:doctor reads {len(entries)} files, ≈{fmt(sum(size for _, size in entries))} tokens; largest: "
        + (", ".join(f"{rel} (≈{fmt(size)})" for rel, size in biggest) or "none"),
        f"- Working files matched: {working}",
        *[line for line in folder_lines(project)[3:] if "never reads" in line],
    ]
    print("\n".join(lines))


def render(values: dict[str, list[str]]) -> str:
    lines = ["---"]
    for key in KEYS:
        items = values[key]
        lines += [f"{key}:", *(f'  - "{item}"' for item in items)] if items else [f"{key}: []"]
    return "\n".join([*lines, "---", "", BODY])


def write(project: Path, location: str, values: dict[str, list[str]], force: bool) -> None:
    try:
        existing = find_config(project, PROJECT_FILES)
    except ValueError as error:
        existing = str(error)
    if existing and not force:
        sys.exit(f"A config already exists ({existing}); rerun with --force to replace it")
    if bad := [item for items in values.values() for item in items if '"' in item or item.startswith("/")]:
        sys.exit(f"Globs must be repo-relative and hold no double quotes: {', '.join(bad)}")
    # Replacing removes every context.md, so no stale copy is left to clash with the new one.
    for name in PROJECT_FILES:
        if (project / name).is_symlink() or (project / name).is_file():
            (project / name).unlink()
    target = project / LOCATIONS[location]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(values), encoding="utf-8")
    if location == "both":
        link = project / ".claude" / "context.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("..") / ".agents" / "context.md")
    print(
        f"Wrote {LOCATIONS[location]}" + (", and .claude/context.md as a symlink to it" if location == "both" else "")
    )
    print()
    check(project)


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("scan", "check"):
        commands.add_parser(name).add_argument("project", type=Path)
    writer = commands.add_parser("write")
    writer.add_argument("project", type=Path)
    writer.add_argument("--location", choices=sorted(LOCATIONS), required=True)
    writer.add_argument("--docs", action="append", required=True, help="a guidance glob; repeat for more")
    writer.add_argument("--also-logged", action="append", help="default: " + ", ".join(DEFAULTS["also_logged"]))
    writer.add_argument("--working-files", action="append", default=[])
    writer.add_argument("--skip-dirs", action="append", default=[])
    writer.add_argument("--lint-allow", action="append", default=[], help="a file allowed to name guidance files")
    writer.add_argument("--force", action="store_true", help="replace an existing config")
    args = parser.parse_args()
    project = args.project.resolve()
    if args.command == "scan":
        scan(project)
    elif args.command == "check":
        check(project)
    else:
        values = {
            "docs": args.docs,
            "also_logged": args.also_logged or list(DEFAULTS["also_logged"]),
            "working_files": args.working_files,
            "skip_dirs": args.skip_dirs,
            "lint_allow": args.lint_allow,
        }
        write(project, args.location, values, args.force)


if __name__ == "__main__":
    main()

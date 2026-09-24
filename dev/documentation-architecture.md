# Documentation Architecture

This document explains how documentation is organized in the Infrahub project to ensure consistency and discoverability.

## Principles

1. **Single Source of Truth**: All technical knowledge lives under `dev/`
2. **AGENTS.md as Gateway**: Component-level `AGENTS.md` files provide quick reference and point to `dev/` for details
3. **The component AGENTS.md is the index**: it lists the guidelines, knowledge docs and guides of its area, each with a line saying what it covers or when to load it. No guideline category keeps a README.md index of its own
4. **Each file loads once, in every harness**: a `CLAUDE.md` only imports the `AGENTS.md` beside it, and a file a harness loads on its own is named, never linked by path

## File Structure

```text
infrahub/
├── AGENTS.md                    # Root entry point, names the component AGENTS.md files and dev/ guidelines
├── CLAUDE.md                    # Only @AGENTS.md, like the CLAUDE.md beside every AGENTS.md below
├── backend/
│   └── AGENTS.md               # Backend overview, lists the dev/ docs for backend work
├── frontend/app/
│   └── AGENTS.md               # Frontend overview, lists the dev/ docs for frontend work
├── docs/
│   └── AGENTS.md               # Conventions for the user-facing docs
├── .agents/
│   ├── rules/                   # Short rules only Claude Code loads, each pointing at its guideline
│   ├── skills/
│   └── commands/
└── dev/
    ├── guidelines/              # How to write code
    │   ├── backend/             # python.md, typing.md, testing.md, component-design.md, ...
    │   └── frontend/            # typescript.md, url-construction.md, ...
    ├── knowledge/               # How the system works
    ├── guides/                  # How to do specific tasks
    ├── adr/                     # Architecture decision records
    └── specs/                   # Feature specifications
```

## How AGENTS.md files reach a session

Every harness loads the root `AGENTS.md` at session start; Claude Code reads it through the root
`CLAUDE.md`. A component `AGENTS.md`, in `backend/`, `frontend/app/`, `docs/` or
`development/grafana/`, reaches:

- **Claude Code** through the `CLAUDE.md` beside it, which Claude Code loads when a file below that
  folder is read. Under its default setting a root `CLAUDE.md` stops Claude Code reading any
  `AGENTS.md` on its own, so a folder without that shim never loads its `AGENTS.md`
- **Codex** through the root `AGENTS.md` naming it. Codex reads only the `AGENTS.md` files from the
  repository root down to its working directory: no `CLAUDE.md`, no rules, no `@` imports

Rules under `.agents/rules/` reach Claude Code only. Each keeps its hard rules to one line apiece and
ends with a pointer to the guideline that holds its full text, which every harness reaches from an
`AGENTS.md`.

## Documentation Flow

### For Agents/Developers Reading Documentation

1. **Start at component level**: the `AGENTS.md` of the area you work in
2. **Pick from its lists**: the Guidelines, Knowledge and Guides entries say what each doc covers
3. **Read specific guidelines**: each is self-contained and focused, and links a related guideline where one builds on another

### For Agents/Developers Writing Documentation

#### ✅ DO

- Put all technical knowledge in `dev/` directories
- List a new doc in its area's `AGENTS.md`, with a line saying what it covers or when to load it
- Open a guideline with a `> Part of:` breadcrumb naming its folder, adding `| Related:` links where useful
- Keep guidelines focused and self-contained
- Give each `AGENTS.md` a `CLAUDE.md` beside it holding only `@AGENTS.md`

#### ❌ DON'T

- Put detailed coding standards in component AGENTS.md files
- Duplicate content between AGENTS.md and dev/ files
- Put anything but `@AGENTS.md` in a `CLAUDE.md`: only Claude Code reads it
- Name an `AGENTS.md`, `CLAUDE.md`, rule, skill or command by path: name the skill or command, and let the harness load the file. An `AGENTS.md` naming the ones below it is the exception
- Create a doc that nothing a harness loads leads to

## Example: Frontend Guidelines

- The frontend `AGENTS.md` lists every frontend guideline under "Guidelines" with what it covers, and its knowledge docs and guides the same way
- `dev/guidelines/frontend/typescript.md` opens with the bare breadcrumb `` > Part of: `dev/guidelines/frontend/` `` and links `route-architecture.md` where the route pattern continues

## Updating the Pattern

When adding new guidelines:

1. Create the guideline file in the appropriate `dev/guidelines/[category]/` directory
2. Add the header: `` > Part of: `dev/guidelines/[category]/` ``, followed by `| Related:` and links where useful
3. List it in the area's `AGENTS.md`, or in the root one's Coding Standards for a cross-cutting guideline, with a line saying when to load it

## Summary

- **Component AGENTS.md**: Quick reference and the index of its area's `dev/` docs, loaded through the `CLAUDE.md` beside it or the root `AGENTS.md` naming it
- **dev/guidelines/[category]/[specific].md**: Focused guideline, opening with a breadcrumb to its folder
- **Rules**: Hard rules for Claude Code, one line each, pointing at the guideline that holds them

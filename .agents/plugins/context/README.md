# context

Records which guidance a Claude Code session loads, and what led to each load, then lets you read, draw and
audit that record.

| Skill | What it does |
|---|---|
| `/context:init` | Scans the repository, asks where its guidance lives, and writes the config below |
| `/context:trace [session id]` | Shows the session's load log, the last 200 lines when it is longer |
| `/context:map [session id]` | Draws the log as a Mermaid diagram and saves it as `context-map.md` beside the log |
| `/context:doctor [session id]` | Forks a 1M-context agent that reads the session history and every doc, works out what the session should have loaded, and reports the difference, starting with what never loaded |

With no argument, each skill uses the current session. Installing the plugin is the opt-in: its hooks start
recording with the next session.

## Configuration

Each repository describes where its guidance lives in a committed `context.md`, as YAML frontmatter, in
`.agents/`, `.claude/`, or both. A repository with both folders keeps the file in `.agents/` and makes
`.claude/context.md` a symlink to it; two separate files are an error. A `context.local.md` beside it, kept
out of git, replaces whole keys for one person. Without a config the defaults apply. `/context:init` writes
the file, and the symlink, from a few questions.

Globs are repo-relative and match paths after symlinks resolve; `**` spans directories, `*` does not, and
`{a,b}` lists alternatives. `CLAUDE.md` and `AGENTS.md` files count as guidance whatever `docs` lists.

| Key | Meaning | Default |
|---|---|---|
| `docs` | Guidance. Every Read of it is logged, and `/context:doctor` reads all of it | `**/AGENTS.md`, `**/CLAUDE.md` |
| `also_logged` | Reads are logged, but the doctor does not read these, such as commands, rules and skills | `.agents/**`, `.claude/**` |
| `working_files` | Material a session works on, such as spec artifacts: logged, never read or judged as guidance | none |
| `skip_dirs` | Directories never scanned, such as submodules | none |

```markdown
---
docs:
  - "<guidance folder>/**"
  - "**/AGENTS.md"
also_logged:
  - ".agents/**"
  - ".claude/**"
working_files:
  - "<specs folder>/**"
skip_dirs:
  - "<submodule>"
---
```

Claude Code's own loading rules are built in, so the log records what it actually loaded:

- At session start, the root `CLAUDE.md`, `.claude/CLAUDE.md` and `CLAUDE.local.md`, the files they import,
  and the rules without `paths:`. It records the root `AGENTS.md` too, when Claude Code reads it: under the
  default instruction-files setting only when no `CLAUDE.md` counts, or always when the person set it to
  read both.
- When a file is read, each folder's `CLAUDE.md` above it, the `AGENTS.md` that the setting makes Claude
  Code read, and the path-scoped rules that match.
- Rules come only from `.claude/rules`, and skills only from `.claude/skills`, because Claude Code reads
  nothing under `.agents/`. The doctor's index flags rules and skills that exist only in `.agents/`.
- Explore and Plan subagents, and custom agents that set `omitClaudeMd`, start without the startup files,
  though nested instruction files and path-scoped rules still reach them on a Read.

## What did not load

`/context:doctor` reports first what never reached the context that needed it. Before the audit, a script
works it out from Claude Code's own record in the transcript: for every file a context read or changed, each
`CLAUDE.md`, `AGENTS.md` and path-scoped rule that applied to it but never loaded there, with the reason.
Typical reasons are an `AGENTS.md` that Claude Code never loads on its own because no `CLAUDE.md` imports it,
a rule that only injects on a Read while the context only wrote the file, and a rule kept in `.agents/rules`.
A subagent's result counts as reaching its parent, so guidance it quotes back is not reported as missing.

Two environment variables change where output goes, per person:

- `CLAUDE_TRACK_DOC_READS_DIR`: write each session's files to `<dir>/<session id>/`
- `CLAUDE_TRACK_DOC_READS_ECHO=0`: no chat notice when a doc is loaded for the first time

## Output

Everything for a session sits in `~/.claude/projects/<project>/<session id>/doc-reads/`:

- `reads.log`: the readable log that `/context:trace` shows
- `reads.jsonl` and `state.json`: the records behind it
- `errors.log`: only when the hook failed, including on a bad config file
- `context-map.md`: from `/context:map`
- `doctor/`: the session summary and doc index `/context:doctor` reads; its report comes back in chat

The scripts need `python3` 3.9 or later and use only the standard library.

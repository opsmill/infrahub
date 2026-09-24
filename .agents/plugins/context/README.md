# context

Records which guidance a Claude Code session loads, and what led to each load, then lets you read, draw and
audit that record.

| Skill | What it does |
|---|---|
| `/context:trace [session id]` | Shows the session's load log, the last 200 lines when it is longer |
| `/context:map [session id]` | Draws the log as a Mermaid diagram and saves it as `context-map.md` beside the log |
| `/context:doctor [session id]` | Forks a 1M-context agent that reads the session history and every doc, works out what the session should have loaded, and reports the difference |

With no argument, each skill uses the current session. Installing the plugin is the opt-in: its hooks start
recording with the next session.

## Configuration

Each repository describes where its guidance lives in `.claude/context.md`, committed, as YAML frontmatter.
A `.claude/context.local.md` with the same frontmatter, kept out of git, replaces whole keys for one person.
Without either file the defaults apply.

Globs are repo-relative and match paths after symlinks resolve; `**` spans directories and `*` does not.

| Key | Meaning | Default |
|---|---|---|
| `docs` | Guidance. Every Read of it is logged, and `/context:doctor` reads all of it | `**/AGENTS.md`, `**/CLAUDE.md` |
| `also_logged` | Reads are logged, but the doctor does not read these, such as commands, rules and skills | `.claude/**` |
| `working_files` | Material a session works on, such as spec artifacts: logged, never read or judged as guidance | none |
| `skip_dirs` | Directories never scanned, such as submodules | none |

```markdown
---
docs:
  - "dev/**"
  - "**/AGENTS.md"
also_logged:
  - ".agents/**"
working_files:
  - "dev/specs/**"
skip_dirs:
  - "vendor"
---
```

Claude Code's own conventions are built in: the root `CLAUDE.md` and the files it imports, nested
`CLAUDE.md` files, `.claude/rules` and `.claude/skills`.

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

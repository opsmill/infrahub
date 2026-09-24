---
name: doctor
description: >-
  Judges whether a Claude Code session had the right guidance in context: works out what it should have loaded from what it did and the whole guidance corpus (every doc the repository's context config names, and the rules and skills by index), then compares that with the session's doc-reads log, the one `/context:trace` shows. Expensive: a forked 1M-context agent reads the whole corpus. TRIGGER when: the user asks to audit a session's context, to check whether a session loaded the right docs, rules or skills, or runs `/context:doctor`. DO NOT TRIGGER when: they only want the log or its diagram → `/context:trace`, `/context:map`; auditing documentation coverage for a feature → `audit-docs`; turning review feedback into internal docs → `harvesting-review`.
disable-model-invocation: true
argument-hint: "[session id]"
compatibility: Needs the context plugin's hooks on when the audited session started (without its log the audit stops after the ideal set), and a model with a 1M-token context window.
context: fork
agent: general-purpose
model: opus[1m]
effort: high
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/doctor_inputs.py *) Bash(git log *) Bash(git show *) Bash(git cat-file *) Bash(git merge-base *) Read Glob Grep
metadata:
  version: 0.1.0
  author: OpsMill
---

# Context doctor

Judge whether a session had the right guidance in context. The method is fixed: from what the session did and the full guidance corpus, work out what it **should** have loaded, then compare that with what the load log says it **did** load. Everything you report comes out of that diff.

## Inputs

!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/doctor_inputs.py ${CLAUDE_SESSION_ID} ${CLAUDE_PROJECT_DIR} $ARGUMENTS`

The files `index.md` says Claude Code loads at session start are already in your context, so don't read them again. The inputs' `Layout` line is the repository's own map of where its guidance lives; the rest of this skill refers to it. The harness also gave you the skill list; `index.md` has each skill's size.

## Steps, in this order

1. **Read the session summary**, whole.
2. **Read every file in the load list** (in `index.md`), whole, with Read calls issued in parallel, about 20 per message. Count them: you report "read N of N". A grep or a partial read doesn't count, because the point is to find guidance nobody pointed you at. Rules and skills stay as index lines; open one only when a finding depends on its body.
3. **Write the ideal set before opening the load log.** Split the session into phases (time range and what the work was). For each phase, list what should have been in context, and why: a file that was touched, a task that was done, or a pointer that applies.
4. **Read the load log**, whole, and put its loads against each phase. If the inputs say the log is missing, stop after the ideal set and say the actual side can't be judged.
5. **Diff.** Anything that should have loaded but didn't, anything that loaded but shouldn't have, and anything that loaded at the wrong time or size becomes a finding. Examples of what that looks like (not a checklist): a missed guideline, an irrelevant load, a duplicate, a huge load, a rule whose `paths:` is too broad or narrow, an `AGENTS.md` pointer to a missing file, or guidance only reachable through a prompt that named it.

## Reading the load log

The log is the `reads.log` the inputs name, the file `/context:trace` prints. It records less than the session loaded, so judge absence only against what it can record.

**What gets a line**

- A Read of a path the `Layout` covers: its docs, also-logged and working-file globs. Reads of any other path are not logged, so their absence means nothing. Check the summary instead.
- A path-scoped rule, or a nested `CLAUDE.md` or `AGENTS.md`, that a Read of any file pulled in. Each is logged once per context, the first time; repeat injections never show.
- A Skill tool call. A slash command the user typed shows only as the prompt's text.
- Not logged: Bash reads (`cat`, `sed`, `grep`), skill bodies, and the user-level `CLAUDE.md` and memory. Before calling a doc missed, check the summary for a Bash read or search of it.

**Layout**

- Line 1 is `# Claude session <id> in <project>, started <UTC time>`.
- Timeline lines start with a local `HH:MM:SS`, the moment the hook wrote them. The inputs give the offset to the summary's UTC.
- Two spaces of indentation per level. A context header is printed only when the context changes, so a run of lines belongs to the last header above it at the next level up.

**Line types**

- `💬 prompt pN: "<text>"` opens a user prompt. A prompt with no logged load under it never appears, so count prompts from the summary. `(prompt not recorded)` stands in for one sent before tracking started.
- `🤖 agent <type>: "<description>"` opens a subagent under the prompt that spawned it. `🤖 agent <type> (start not recorded)` is a subagent whose start was missed, which is how a forked skill appears. A subagent is its own context: it doesn't see what the main agent loaded.
- `📄 read <path>`, optionally followed by `(lines a-b)` or `(from line N)` for a partial read, then `(read N)` when this context has read the file before, then `· path via <files>` listing already-loaded files that name the path. `path via` is where the path could have come from, not why it was read.
- `📏 rule <path> ← <file>`: a path-scoped rule, pulled in by the Read of `<file>`.
- `📘 loaded <path> ← <file>`: a nested `CLAUDE.md` or `AGENTS.md`, pulled in by the Read of `<file>`, or a file one of them imports, where `<file>` is the importing file.
- `🧩 skill <name> <args>`: a Skill tool call at that point.
- `── docs read this session (N files, M loads) ──` opens a closing block. It has no timestamps, lists `startup:` (the root instruction files Claude Code loads under the person's instruction-files setting, their imports, and the rules without `paths:`, assumed in every context), and repeats the timeline. It is written again at every session end, so a resumed session carries several. Read the timeline, and take `startup:` from the last block.

**Lines to leave out**

- When the audited session is the one that invoked you, the log ends with this audit: a `💬 prompt pN: "/context:doctor…"` and an agent block of about a hundred reads under it. Stop before it.
- Reads of the `Layout`'s working files, such as spec artifacts, are the session's own material. They are not guidance, so they stay out of the ideal set and never count as irrelevant loads.

**Duplicates**

A `(read N)` line is a repeat of that file in the same context, unless a compaction came in between (the summary lists the main agent's compactions), since a compaction drops the earlier copy. The other duplicate is the same content reaching one context through two files, such as a rule and the guideline it summarises, which you can only spot because you read both. Rules and nested `CLAUDE.md` files are logged once per context by construction, so the log can't show them injected twice. Weigh size with the token figures in `index.md` and what you read, times the number of contexts that loaded it.

The docs tree is the checkout as it is now. When a finding depends on what the session could see then (another branch, an older commit), check with `git log`, `git show <branch>:<path>` or `git merge-base`, and say which version you judged against.

## Report

Return it as your final message, in this shape:

```text
# Context doctor · <session id>
## Verdict
<three lines at most>
## Load check
Read <N> of <N> load-list files · docs tree <path> · <version caveat, if any>
## Ideal set
| Phase (UTC) | Work | Should have been in context | Why | Loaded? |
## Findings
### 1. <one-line claim>
- Evidence: log lines (time and text), summary lines (time)
- Cost: tokens for an extra or duplicate load, or the risk for a missed one
- Root cause: file and line, glob, or pointer
- Fix: the concrete edit
- Confidence: high / medium / low, and what would change it
## Noticed, outside context fit
- <one line each: content gaps, process issues>
```

Rank findings by impact. Propose edits; don't make any.

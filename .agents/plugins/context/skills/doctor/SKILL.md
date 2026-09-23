---
name: doctor
description: >-
  Judges whether a Claude Code session had the right guidance in context: works out what it should have loaded from what it did and the whole guidance corpus (every `dev/` doc outside `dev/specs`, every `AGENTS.md`, and the rules and skills by index), then compares that with the session's doc-reads log, the one `/context:trace` shows. Expensive: a forked 1M-context agent reads the whole corpus. TRIGGER when: the user asks to audit a session's context, to check whether a session loaded the right docs, rules or skills, or runs `/context:doctor`. DO NOT TRIGGER when: they only want the log or its diagram → `/context:trace`, `/context:map`; auditing documentation coverage for a feature → `audit-docs`; turning review feedback into internal docs → `harvesting-review`.
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

The root `AGENTS.md` is already in your context through `CLAUDE.md`, so don't read it again. The harness also gave you the skill list; `index.md` has each skill's size.

## Steps, in this order

1. **Read the session summary**, whole.
2. **Read every file in the load list** (in `index.md`), whole, with Read calls issued in parallel, about 20 per message. Count them: you report "read N of N". A grep or a partial read doesn't count, because the point is to find guidance nobody pointed you at. Rules and skills stay as index lines; open one only when a finding depends on its body.
3. **Write the ideal set before opening the load log.** Split the session into phases (time range and what the work was). For each phase, list what should have been in context, and why: a file that was touched, a task that was done, or a pointer that applies.
4. **Read the load log**, whole, and put its loads against each phase. If the inputs say the log is missing, stop after the ideal set and say the actual side can't be judged.
5. **Diff.** Anything that should have loaded but didn't, anything that loaded but shouldn't have, and anything that loaded at the wrong time or size becomes a finding. Examples of what that looks like (not a checklist): a missed guideline, an irrelevant load, a duplicate, a huge load, a rule whose `paths:` is too broad or narrow, an `AGENTS.md` pointer to a missing file, or guidance only reachable through a prompt that named it.

## Reading the load log

The log is the `reads.log` the inputs name, the file `/context:trace` prints. Each line starts with the local time (`HH:MM:SS`); the inputs give the offset to the summary's UTC. Indentation shows where a load happened:

- `💬 prompt pN: "…"` opens a user prompt; the lines indented under it happened while working on it.
- `🤖 agent <type>: "<description>"` opens a subagent under the prompt that spawned it (`(start not recorded)` when its start was missed). A subagent is its own context: it doesn't see what the main agent loaded.
- `📄 read <path> (lines a-b) (read N) · path via <files>`: a Read of that file, partial when lines are given. `(read N)` means this is the Nth Read of it in this context. `path via` (or `← <files>`) lists already-loaded files that name the path: where the path could have come from, not necessarily why it was read.
- `📏 rule <path> ← <file>`: a path-scoped rule that the Read of `<file>` matched, logged once per context.
- `📘 loaded <path> ← <file>`: a nested `CLAUDE.md`, or a file it imports, loaded by the Read of `<file>`, logged once per context.
- `🧩 skill <name> <args>`: a skill invoked at that point.
- The closing block `── docs read this session (N files, M loads) ──` repeats the loads and lists the `startup:` files.

Duplicates come in two forms, and you can see both. One is a `(read N)` line: the context already held that file, unless a compaction came in between (the summary lists the main agent's compactions), since a compaction drops the earlier copy. The other is the same content reaching one context through two files, such as a rule and the guideline it summarises, which you can only spot because you read both. Weigh size with the token figures in `index.md` and what you read, times the number of contexts that loaded it.

Loads through Bash (`cat`, `sed`, `grep`) don't appear in the log. Before calling a doc missed, check the summary for a Bash read or search of it.

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

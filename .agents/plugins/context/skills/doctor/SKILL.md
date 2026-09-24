---
name: doctor
description: >-
  Judges whether a Claude Code session had the right guidance in context: works out what it should have loaded from what it did and the whole guidance corpus (every doc the repository's context config names, and the rules and skills by index), then compares that with the session's doc-reads log, the one `/context:trace` shows. Expensive: a forked 1M-context agent reads the whole corpus. TRIGGER when: the user asks to audit a session's context, to check whether a session loaded the right docs, rules or skills, or runs `/context:doctor`. DO NOT TRIGGER when: they only want the log or its diagram → `/context:trace`, `/context:map`; the repository has no context config yet → `/context:init`.
disable-model-invocation: true
argument-hint: "[session id]"
compatibility: Needs the context plugin's hooks on when the audited session started (without its log the audit stops after the ideal set), and a model with a 1M-token context window.
context: fork
agent: context:doctor
model: opus[1m]
effort: high
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/doctor_inputs.py *) Read Glob Grep
metadata:
  version: 0.1.0
  author: OpsMill
---

# Context doctor

Judge whether a session had the right guidance in context. The method is fixed: from what the session did and the full guidance corpus, work out what it **should** have loaded, then compare that with what it **did** load. Everything you report comes out of that diff, and what did not load comes first: guidance the work needed and never had is the most serious thing you can find.

Claude Code does all the loading: it injects instruction files and rules, and the session reads docs. The plugin only records what happened; it injects nothing. So a loading problem is always in an instruction file, a rule's `paths:`, a pointer, or Claude Code's own behaviour, never in the plugin.

## Inputs

!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/doctor_inputs.py ${CLAUDE_SESSION_ID} ${CLAUDE_PROJECT_DIR} $ARGUMENTS`

`not-loaded.md` lists the instruction files and rules that applied to files a context read or changed but never reached that context, with the reason each time; it is computed from Claude Code's own record in the transcript, not guessed. The files `index.md` says Claude Code loads at session start are already in your context, so don't read them again. The inputs' `Layout` line is the repository's own map of where its guidance lives; the rest of this skill refers to it. `index.md` lists the skills the session was offered, with sizes; the harness gave you the descriptions of those installed here.

## Steps, in this order

1. **Read the session summary and `not-loaded.md`**, whole.
2. **Read every file in the load list** (in `index.md`), whole, with Read calls issued in parallel, about 20 per message. Count them: you report "read N of N". A grep or a partial read doesn't count, because the point is to find guidance nobody pointed you at. Rules and skills stay as index lines; open one only when a finding depends on its body.
3. **Write the ideal set before opening the load log.** Split the session into phases (time range and what the work was). For each phase, list what should have been in context, and why: a file that was touched, a task that was done, or a pointer that applies.
4. **Read the load log**, whole, and put its loads against each phase. If the inputs say the log is missing, stop after the ideal set and say the actual side can't be judged.
5. **Diff, starting with what did not load.** Every item in `not-loaded.md` goes into the report's Not loaded section, confirmed against the log and the summary or explained away, never dropped. Add every file from your ideal set that no context that needed it held. Then anything that loaded but shouldn't have, and anything that loaded at the wrong time or size, becomes a finding. Examples of what that looks like (not a checklist): a missed guideline, an irrelevant load, a duplicate, a huge load, a rule whose `paths:` is too broad or narrow, an `AGENTS.md` pointer to a missing file, or guidance only reachable through a prompt that named it.

## Reading the load log

The log is the `reads.log` the inputs name, the file `/context:trace` prints. It records less than the session loaded, so judge absence only against what it can record.

**What gets a line**

- A Read of a path the `Layout` covers: its docs, also-logged and working-file globs. Reads of any other path are not logged, so their absence means nothing. Check the summary instead.
- A path-scoped rule, or a nested `CLAUDE.md` or `AGENTS.md`, that a Read of any file pulled in. Each is logged once per context, the first time; repeat injections never show.
- A Skill tool call. A slash command the user typed shows only as the prompt's text.
- Not logged: Bash reads (`cat`, `sed`, `grep`), skill bodies, and the user-level `CLAUDE.md` and memory. Before calling a doc missed, check the summary for a Bash read or search of it.

**Layout**

- Line 1 is `# Claude session <id> in <project>, started <UTC time>`.
- Timeline lines start with a local `HH:MM:SS`: an entry's is when it loaded, a context header's is when its prompt or subagent started. The summary uses the same clock.
- Two spaces of indentation per level. A context header is printed only when the context changes, so a run of lines belongs to the last header above it at the next level up.

**Line types**

- `💬 prompt pN: "<text>"` opens a user prompt. A prompt with no logged load under it never appears, so count prompts from the summary. `(prompt not recorded)` stands in for one sent before tracking started.
- `🤖 agent <type>: "<description>"` opens a subagent under the prompt that spawned it. `🤖 agent <type> (start not recorded)` is a subagent whose start was missed, which is how a forked skill appears. A subagent is its own context: it doesn't see what the main agent loaded. Explore and Plan subagents, and custom agents whose definition sets `omitClaudeMd`, start without the startup instruction files. Nested `CLAUDE.md` and `AGENTS.md` files and path-scoped rules still reach them on a Read, unless the same message also Reads that file itself, when Claude Code skips the injection; the log still shows the load, and the content is in context either way.
- A subagent's result flows back into its parent: whatever its final message quotes is in the parent's context from the moment it arrives. A background subagent's result shows as `💬 prompt pN: "(subagent result) …"`, and the summary shows it as `subagent result`. `not-loaded.md` lists the files a result quoted in full; treat those as held by the parent from then on.
- `📄 read <path>`, optionally followed by `(lines a-b)` or `(from line N)` for a partial read, then `(read N)` when this context has read the file before, then `· path via <files>` listing already-loaded files that name the path. `path via` is where the path could have come from, not why it was read.
- `📏 rule <path> ← <file>`: a path-scoped rule, pulled in by the Read of `<file>`.
- `📘 loaded <path> ← <file>`: a nested `CLAUDE.md` or `AGENTS.md`, pulled in by the Read of `<file>`, or a file one of them imports, where `<file>` is the importing file.
- `🧩 skill <name> <args>`: a Skill tool call at that point.
- `── docs read this session (N files, M loads) ──` opens a closing block. It has no timestamps, lists `startup:` (the root instruction files Claude Code loads under the person's instruction-files setting, their imports, and the rules without `paths:`, in every context except those that start without project instructions), and repeats the timeline. It is written again at every session end, so a resumed session carries several. Read the timeline, and take `startup:` from the last block.

**Lines to leave out**

- When the audited session is the one that invoked you, the log ends with this audit: a `💬 prompt pN: "/context:doctor…"` and an agent block under it that reads the whole load list. Stop before it.
- Reads of the `Layout`'s working files, such as spec artifacts, are the session's own material. They are not guidance: they stay out of the ideal set, never count as irrelevant loads, and you don't read them yourself.

**Duplicates**

A `(read N)` line is a repeat of that file in the same context, unless a compaction came in between (the summary lists the main agent's compactions), since a compaction drops the earlier copy. The other duplicate is the same content reaching one context through two files, such as a rule and the guideline it summarises, which you can only spot because you read both. Rules and nested `CLAUDE.md` files are logged once per context by construction, so the log can't show them injected twice. Weigh size with the token figures in `index.md` and what you read, times the number of contexts that loaded it.

The docs tree is the checkout as it is now, and the inputs' `Docs tree` line gives its branch next to the session's. You can't read other versions: when the branches differ, or a finding depends on a doc that may have changed since the session, say so in the Load check line and judge against the tree as it is.

## Report

Return it as your final message, in this shape:

```text
# Context doctor · <session id>
## Verdict
<three lines at most; the first names every file in Not loaded, or says nothing was missing, and then whether any of it mattered>
## Not loaded
| What | Context | Applies to | Why it did not load | What it would have changed | Fix |
<one row per item in not-loaded.md, confirmed or with why it did not matter, plus each ideal-set file no context that needed it held; write "Nothing" only when both are empty>
## Load check
Read <N> of <N> load-list files · docs tree <path> · <version caveat, if any>
## Ideal set
| Phase (local time) | Work | Should have been in context | Why | Loaded? |
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

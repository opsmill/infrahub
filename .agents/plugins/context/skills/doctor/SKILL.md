---
name: doctor
description: >-
  Audits a repository's agent guidance and how a Claude Code session loaded it: a forked read-only agent audits the session, a script lints the repository, and the two reports are merged, starting with what never loaded. Expensive: the session audit reads the whole guidance corpus with a 1M-context model. TRIGGER when: the user asks to audit a session's context, to check whether a session loaded the right docs, rules or skills, or to lint or check the repository's agent guidance, or runs `/context:doctor`. DO NOT TRIGGER when: they only want the log or its diagram → `/context:trace`, `/context:map`; the repository has no context config yet → `/context:init`.
disable-model-invocation: true
argument-hint: "[session id]"
compatibility: Needs the context plugin's hooks on when the audited session started, and a model with a 1M-token context window for the session audit.
allowed-tools: Skill
metadata:
  version: 0.1.0
  author: OpsMill
---

# Context doctor

Run the two halves of the audit, then merge them. Work only through them: don't read files or run commands yourself.

1. In one message, invoke both skills:
   - `context:audit-session`, with the arguments `${CLAUDE_SESSION_ID} $ARGUMENTS` exactly as written here
   - `context:lint-repo`, with no arguments
2. The lint's lines arrive with its skill; the audit's report comes back when its forked agent finishes. Wait for both. If one fails, say so under its heading and keep the other.
3. Reply with the merged report in this shape, and nothing else:

```text
# Context doctor · <the audited session id, from the session audit's title>
## Verdict
<three lines at most: first every file that never loaded, from the session audit's verdict; then the lint's error and warning counts and its first error; then what to fix first>
<the session audit's report, whole, from its first heading down>
# Repository lint
<the lint's lines, unchanged, inside a fenced text block>
```

Copy the audit's report and the lint's lines whole: don't shorten, reorder or reword them.

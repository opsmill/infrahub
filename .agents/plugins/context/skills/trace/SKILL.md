---
name: trace
description: >-
  Shows the doc-reads log of a Claude Code session: every internal doc, path-scoped rule and nested `CLAUDE.md` it loaded, under the prompt or subagent that loaded it. TRIGGER when: the user asks what docs, rules or context a session loaded, or runs `/context:trace`. DO NOT TRIGGER when: they want a diagram of why each doc loaded → `/context:map`; they want to know whether the loads were the right ones → `/context:doctor`.
disable-model-invocation: true
argument-hint: "[session id]"
compatibility: Needs the context plugin's hooks on when the session started; they write the log this shows.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context_trace.py *)
metadata:
  version: 0.1.0
  author: OpsMill
---

# Context trace

!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context_trace.py ${CLAUDE_SESSION_ID} $ARGUMENTS`

Reply with the output above exactly as printed, in one `text` code block, and nothing else. When its first line starts with `Last 200 of`, add one line after the block saying the full log is at the path that line names.

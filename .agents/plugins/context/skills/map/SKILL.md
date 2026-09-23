---
name: map
description: >-
  Draws a Mermaid diagram of the internal docs a Claude Code session loaded, in order, and what led to each one: the Read that pulled in a rule or nested `CLAUDE.md`, or the already-loaded file, prompt or subagent brief that named the doc. TRIGGER when: the user asks why a session loaded a doc, wants its context as a diagram, or runs `/context:map`. DO NOT TRIGGER when: they want the raw log → `/context:trace`; they want to know whether the loads were the right ones → `/context:doctor`.
disable-model-invocation: true
argument-hint: "[session id]"
compatibility: Needs the context plugin's hooks on when the session started; they write the log this reads.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context_map.py *)
metadata:
  version: 0.1.0
  author: OpsMill
---

# Context map

!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context_map.py $ARGUMENTS --default-session ${CLAUDE_SESSION_ID} --save`

Reply with the Markdown above unchanged, from its `# Docs read in session` heading to the end of the `mermaid` block, then one line naming the file from its `Saved to` line.

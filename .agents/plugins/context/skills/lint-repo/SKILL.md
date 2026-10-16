---
name: lint-repo
description: >-
  The repository half of `/context:doctor`: a script checks how the repository organises its agent guidance against rules that make every harness load each file once. Only `/context:doctor` invokes it. DO NOT TRIGGER otherwise, even when the user asks to lint the guidance: that is `/context:doctor`, or the plugin's `scripts/context_lint.py` run directly.
user-invocable: false
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context_lint.py *)
metadata:
  version: 0.1.0
  author: OpsMill
---

# Repository lint

!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context_lint.py ${CLAUDE_PROJECT_DIR}`

The lines above are the repository lint, from a script; each finding says what to change. `/context:doctor` puts them in its report unchanged.

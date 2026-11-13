---
name: init
description: >-
  Sets up the context plugin for a repository: scans where its agent guidance lives, asks a few questions, and writes the plugin's `context.md` in `.agents/`, `.claude/`, or both through a symlink. TRIGGER when: the user asks to set up, configure or initialise the context plugin, runs `/context:init`, or another context skill reports that the repository has no config. DO NOT TRIGGER when: the repository is configured and the user wants to see or audit a session → `/context:trace`, `/context:map`, `/context:doctor`.
disable-model-invocation: true
compatibility: Writes the config into the repository; the person reviews and commits it.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context_init.py *) AskUserQuestion Read
metadata:
  version: 0.1.0
  author: OpsMill
---

# Context init

!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context_init.py scan ${CLAUDE_PROJECT_DIR}`

Set up the plugin's config for this repository from the scan above and the person's answers. Write nothing before they answer.

1. If the scan shows an existing config, show its effective layout and ask whether to replace it. Stop if they say no.
2. Ask these four questions in one AskUserQuestion call. Build the options from the scan, put the recommended one first, and rely on Other for anything the scan missed:
   - **Guidance** (multiSelect): which folders hold guidance for agents and developers, the docs `/context:doctor` reads whole. Offer the largest such folders from the scan, and `**/AGENTS.md`. User-facing documentation is not guidance, and neither is anything offered as working material.
   - **Working material** (multiSelect): folders a session works on rather than follows, such as specs and plans. Offer the scan's working-material candidates, and None.
   - **Skip** (multiSelect): folders never to scan, such as submodules and vendored code. Offer the scan's skip candidates, and None.
   - **Location** (single choice): offer `.agents/context.md` with `.claude/context.md` as a symlink to it, `.claude/context.md` only, and `.agents/context.md` only. Recommend the symlink when the repository has `.agents/`, else `.claude/context.md`.
3. Turn the answers into values: a folder becomes `<folder>/**`, a pattern stays as given, and None adds nothing. `also_logged` keeps its default, `.agents/**` and `.claude/**`, unless the person asked for something else.
4. Write the config with one command. Quote every glob so the shell leaves it alone, repeat a flag once per value, and add `--force` only when the person agreed to replace an existing config:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context_init.py write ${CLAUDE_PROJECT_DIR} --location <location> --docs "<guidance glob>" [--docs "<guidance glob>" ...] [--working-files "<glob>" ...] [--skip-dirs "<folder>" ...]
   ```

   `--location` is `both`, `claude` or `agents`.
5. Show the check that `write` prints. Then tell the person to commit the config, and the symlink with `both`, and that recording starts with their next session once the plugin is installed. Then name what the scan found Claude Code never loads: each `AGENTS.md` that never loads on its own, which a `CLAUDE.md` containing `@AGENTS.md` in the same folder fixes, and each `.agents/` folder not linked from `.claude/`, which a symlink fixes. A `context.local.md` for personal overrides belongs in `.gitignore`.

---
description: Phase of the opsmill-prep workflow — correct spec.md after the alignment check found that it drifted from the request.
---

## User Input

```text
$ARGUMENTS
```

## Outline

You run **one phase** of the `opsmill-prep` workflow: **Realign the spec**. The workflow file (`.specify/workflows/opsmill-prep/workflow.yml`) runs the other phases as separate steps and decides when a phase is repeated, so do only what this file describes, then stop.

Nobody can answer a question during this run. Wherever a choice comes up, use your best judgment and continue.

Do not commit: the workflow commits what this phase wrote.

The user input above is the original request. The alignment check of the previous pass found significant drift between that request and `spec.md`.

The feature directory is the `feature_directory` recorded in `.specify/feature.json`.

1. Read `alignment-check.md` in the feature directory: its findings list what the spec must fix.
2. Invoke the `speckit-specify` skill with an augmented input that holds:
   - the original request (and the body of the PRD when the request is a URL);
   - an explicit list of the drift findings to fix: requirements to add, off-scope items to remove, changed semantics to revert, dropped acceptance criteria to restore.
3. The skill must update the existing `spec.md` in place: same feature directory, same branch. Do not create a second spec.

Do not refresh the plan or the tasks: the workflow runs those phases next.

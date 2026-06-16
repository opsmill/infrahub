# Investigation

These are the shared investigation steps for bug analysis.
Read this file when directed by your main prompt.

## Issue clarity check

Verify the issue has enough information to work with:

| Required | Description |
|----------|-------------|
| **Clear problem statement** | Can you understand what the bug actually is? |
| **Reproduction path** | Are there steps to reproduce, OR can you infer them from the description? |
| **Expected vs actual** | Is it clear what should happen vs what happens? |

Rate the clarity:
- **CLEAR**: intent, reproduction scenario, and expected behavior are understandable (even if some details like affected release are missing).
- **UNCLEAR**: the intent and reproduction scenario are not understandable.

If the bug is UNCLEAR, **STOP** here and escalate as described in your main prompt.

## Investigate the codebase

1. Read root `AGENTS.md` and `dev/documentation-architecture.md` in order to determine which code packages are related to the issue. Then:
   - If you can determine the code package related to the bug, rate the code identification step as RESOLVED.
   - If you cannot determine the code package related to the bug, rate the code identification step as EXPLORATION REQUIRED, and explore the code base.

2. Read the relevant source files in the affected area to understand the current behavior.

3. Identify the most likely root cause(s) -- point to specific files and lines.
   - If you **cannot** identify a root cause after exploration, **STOP** and escalate
     as described in your main prompt.

4. Formulate a fix strategy. This is NOT the exact code -- it is the recommended approach:
   - **Approach:** What should the fixer do and where? Reference existing functions/methods
     that should be reused rather than reimplemented.
   - **Scope:** Which files/functions need changes? How large should the change be?
   - **Do NOT:** List common wrong approaches (e.g., adding a guard clause when the real
     fix is a missing validation, creating new abstractions when an existing one should be reused).

## Analysis template

Write the analysis output using this structure (replace all `<placeholders>`):

````markdown
## Root cause analysis for #<issue_number>

**Issue:** <issue title>
**Based on:** `<commit SHA of origin/stable>`
**Bug clarity:** CLEAR
**Code identification:** RESOLVED | EXPLORATION REQUIRED

### Root cause
<one-sentence summary>

### Affected files
- `path/to/file.ext` -- line X: <why this is the culprit>

### Explanation
<detailed reasoning>

## Fix strategy

**Approach:** <recommended fix approach -- explain WHAT to do and WHERE, not the exact code>

**Scope:** <which files/functions should need changes, and roughly how large the change should be>

**Do NOT:**
- <guardrail 1 -- common wrong approach to avoid>
- <guardrail 2 -- unnecessary refactoring to avoid>

## Notes for downstream steps
<edge cases, risks, or constraints the test-writer and fixer should know about>
````

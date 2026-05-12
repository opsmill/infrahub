---
description: "Reconcile implementation drift by updating the feature's own spec, plan, and tasks"
scripts:
  sh: ../../scripts/bash/check-prerequisites.sh --json --paths-only --include-tasks
  ps: ../../scripts/powershell/check-prerequisites.ps1 -Json -PathsOnly -IncludeTasks
---
Act as the **Chief Software Architect** and **Implementation Auditor**.
A feature implementation has landed, but "artifact drift" has been discovered (e.g., missing routes, updated behavior, or unlinked UI). Your goal is to **reconcile** this drift by surgically amending the feature's own specification, plan, and task artifacts.

## User Input

```text
$ARGUMENTS
```

### Input Parsing

The input `$ARGUMENTS` is a **Gap Report** — a natural language description of what is missing or changed in the implementation versus the documentation.

**Examples:**
- "Backend + tests for Invoice Settings exist; React screen scaffolded. Users can't navigate to it. Need sidebar link + route."
- "The /api/v1/settings endpoint now requires an 'org_id' header not in the original plan."

If `$ARGUMENTS` contains any of these flags, respect them (optional):
- `--spec-only` — update only `spec.md`
- `--plan-only` — update only `plan.md`
- `--tasks-only` — update only `tasks.md`

If `$ARGUMENTS` is empty, output `ERROR: No gap report provided. Usage: /speckit.reconcile.run [gap report text]` and stop.

---

## Step 0: Discovery & Setup (Gate)

### 0.1 Resolve Paths

Run `{SCRIPT}` to identify the active feature directory and its artifacts. This script is mandatory for path discovery. If the script is missing, stop and inform the user.

Derive absolute paths for:
- `FEATURE_DIR` (e.g., `specs/###-feature-name/`)
- `FEATURE_SPEC` (`FEATURE_DIR/spec.md`)
- `IMPL_PLAN` (`FEATURE_DIR/plan.md`)
- `TASKS_FILE` (`FEATURE_DIR/tasks.md`)

**Validation**: Ensure `spec.md` and `plan.md` exist. If either is missing, stop with:
> ⚠️ Missing required files in `FEATURE_DIR`. Expected: spec.md, plan.md.
> Run `/speckit.specify` and `/speckit.plan` first.

If `tasks.md` does not exist, create it with a `## Remediation: Gaps` heading before appending tasks.

### 0.2 Load Context

Read `FEATURE_SPEC`, `IMPL_PLAN`, and `TASKS_FILE`.

Also read `.specify/memory/constitution.md` if it exists. If found, extract MUST-level constraints and Architecture Standards. These are enforced in Step 1 — any remediation item that conflicts with a MUST principle is flagged as CRITICAL:
```
🔴 CONSTITUTION CONFLICT: [remediation item] conflicts with [principle]
→ This must be resolved in Step 2 clarification before edits proceed.
```

---

## Step 1: Gap Normalization

Analyze the user's **Gap Report** and normalize it into structured remediation items:

| Category | Typical Issues | Action |
|----------|----------------|--------|
| **Wiring & Navigation** | Missing routes, menu items, sidebar links | Add to `plan.md`, create tasks in `tasks.md` |
| **Contracts** | API field mismatches, missing headers | Update `plan.md` contracts, create tasks |
| **Acceptance Criteria** | Implementation behaves differently than planned | Update `spec.md` scenarios/criteria |
| **Test Coverage** | New wiring/navigation without verification | Add task for Integration Test |
| **Logic/UX** | Success toasts missing, error handling gaps | Add tasks for implementation |

For each normalized item, verify it does not conflict with any MUST-level constitution constraint loaded in Step 0.2. Flag any conflicts as CRITICAL and include them in Step 2 clarification.

---

## Step 2: Clarify (Exactly Once; Max 5 Questions)

If the gap report is ambiguous (e.g., "the button doesn't work" without saying which button), ask targeted questions.

Use this format and **wait for answers**:

```markdown
## Question [N]: [Topic]
**Context**: [Relevant implementation detail]
**Decision Needed**: [1 sentence]
**Suggested Answers**: [Table with Option A/B/C]

**Your choice**: _[Wait for user response]_
```

**Rules:**
- Max 5 questions.
- Max 3 unresolved `NEEDS CLARIFICATION` markers in output — beyond that, pick reasonable defaults and note them in the Sync Impact Report.
- Proceed with reasonable defaults if questions aren't strictly necessary.

---

## Step 3: Impact Map

Before making any edits, produce a brief impact map:

```markdown
### Sync Impact Map
| Artifact | Changes | Tasks Generated |
|----------|---------|-----------------|
| `spec.md` | Update AC-04, add User Scenario "Error Handling" | None |
| `plan.md` | Add Route `/settings`, update API contract | None |
| `tasks.md` | Append remediation tasks | T045, T046, T047 |
```

---

## Step 4: Reconciliation (Surgical Edits)

**Constraint**: Operate strictly in place. Do not create branches, switch branches, or run feature-creation scripts. All edits target existing files in `FEATURE_DIR`.

### 4.1 Update Specification (`spec.md`)
- **Acceptance Criteria**: Amend existing criteria or add new ones to reflect the shipped reality.
- **User Scenarios**: Add missing scenarios discovered during implementation (e.g., specific edge cases).
- **Revision Note**: Add a block at the bottom:
  ```markdown
  ### Revision: Implementation Sync [YYYY-MM-DD]
  - Reason: [Summary of drift reconciled]
  ```

### 4.2 Update Plan (`plan.md`)
- **Routing & Navigation**: Add any missing routes, endpoints, or UI wiring details.
- **Integration Contracts**: Update API schemas, request/response headers, or payloads.
- **Testing Strategy**: Ensure the strategy covers the newly identified gaps.
- **Revision Note**: Append a revision note (same format as spec.md) if plan sections were modified.

### 4.3 Update Tasks (`tasks.md`)
This is the most critical step. Create remediation tasks to close the drift.

**Task Formatting**:
`- [ ] T{NNN} [P] [{story}] {action verb} {what} in {exact/file/path.ext} [Sync: Gap Report]`

Where `[P]` is an optional priority flag — include it only for tasks that are blocking or high-urgency. Omit for normal priority. The `[Sync: Gap Report]` tag is always appended for traceability.

**Rules for Tasks**:
1. **Increment IDs**: Find the highest `T###` in `tasks.md`. Start new tasks from `max + 1`. Never reuse or renumber.
2. **Phase Placement**: Place new tasks under the relevant User Story phase (e.g., `## [US2] Settings Dashboard`). If no phase fits, create a `## Remediation: Gaps` section at the end.
3. **Exact Paths**: Every task MUST include an exact file path where the change is needed.
4. **Mandatory Integration Test**: If you identified a **Wiring & Navigation** gap, you MUST add a task for an Integration Test to verify it.

---

## Step 5: Sync Impact Report

Output the final report:

```markdown
# Sync Impact Report

## Changed Files
| File (absolute path) | Change Summary |
|----------------------|----------------|
| `/absolute/path/to/spec.md` | Updated AC, Scenarios |
| `/absolute/path/to/plan.md` | Updated Routing/Contracts |
| `/absolute/path/to/tasks.md` | Added [N] remediation tasks |

## New Remediation Tasks
[List the new tasks added, e.g.]
- **T045**: Add sidebar link in `src/components/Sidebar.tsx`
- **T046**: Update router in `src/router/index.ts`
- **T047**: Integration test: navigate to Settings in `tests/integration/navigation.test.ts`

## Outstanding Decisions
[List any `NEEDS CLARIFICATION` items or "None"]

## Next Step
[Recommend based on what changed:]
- If remediation tasks were added → `/speckit.implement` to execute them
- If plan was significantly updated → `/speckit.plan` to review architecture
- If only spec was updated → Review changes and proceed with implementation
```

---

## Done Criteria
- Gap report parsed and categorized.
- Feature's own `spec.md` and `plan.md` surgically updated.
- `tasks.md` updated with incremented `T###` IDs and exact file paths.
- Mandatory integration test task added for wiring gaps.
- Revision note added to artifacts.
- Sync Impact Report printed.

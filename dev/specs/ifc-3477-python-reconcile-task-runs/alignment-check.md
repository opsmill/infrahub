# Spec/Ask Alignment Check: One branch deletion records the same number of task runs whatever the number of open branches

**Date**: 2026-11-04

## Source

- The PRD in [issue #11165, comment 6470511683](https://github.com/opsmill/infrahub/issues/11165#issuecomment-6470511683), fetched with `gh api repos/opsmill/infrahub/issues/comments/6470511683`.
- The bug report in [#11165](https://github.com/opsmill/infrahub/issues/11165), for context.

Compared against [spec.md](spec.md) after the critique and after [tasks.md](tasks.md) was generated.

## Verdict

⚠️ MINOR DRIFT (proceeding)

Every PRD requirement is in the spec with the same meaning:

- FR-001 to FR-005, SC-001 to SC-003;
- the two user journeys and their acceptance criteria;
- the edge cases, the out-of-scope list, the delivery order;
- the testing decisions and the governance gates.

The differences are corrections of three factual statements in the PRD, made from code evidence during the critique, and additions that set no new requirement. No PRD requirement was dropped or softened.

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| Low | changed | User journeys, Priority 1, acceptance: "every other automation stays as it was" | User Story 1, scenario 3 | The PRD statement is false when the deleted branch had its own repository commit. The default-branch automation excludes that branch, and the reconcile removes the exclusion after the deletion, as it does today. The spec now says that every other automation matches what a full reconcile builds, which is the PRD's own SC-002 wording. FR-002 is unchanged. |
| Low | changed | Edge cases: a worker's registry still lists the deleted branch, "logs one warning per transform" | Edge Cases | The query on the deleted branch can still return the transform from `main`, so whether a warning is logged is not known. The spec says so. The PRD's statement that this spec does not change the case is kept. |
| Low | changed (more precise) | FR-005, and Implementation decisions: "the existing failure names the branch" | User Story 3, scenario 2; research R4 | The spec keeps "no new error type" and says where the branch appears: in a note at the end of the traceback in the run's error log. The run's state message keeps the original error text. This follows from the PRD's own decision to keep the existing error type. |
| Low | added | User story 6 and Constitution alignment, documentation requirements | FR-006 | The PRD's changelog requirement became a functional requirement, so that tasks and review cover it. It keeps the PRD's scope: a `fixed` fragment that names `infrahub tasks flush flow-runs`. |
| Low | added | Open questions, two `[NEEDS CLARIFICATION]` | Resolved Clarifications | Both questions are answered from the Prefect 3.7.5 and 3.8.6 sources and the PostgreSQL documentation, with links. The details go in the pull request description for the release notes, which matches the PRD's "a release note would rely on the answer". |
| Low | added | — | Edge Cases (`trigger-configure-all`, UUID wiring); Out of Scope (hardware requirements page); Delivery Order (`develop` callers) | These are observations from the code. Each states that this spec does not change the behavior, or lists it as a follow-up. None adds a requirement. |
| Low | missing (fixed) | Related work | Related Work | The spec had no Related Work section. It was added in the same commit as this report, with the PRD's links. |

## Action

Proceed. No remediation pass was needed, and the counter stays at 0.

The three corrections make the spec match the code. They were made during the critique and are recorded in [critiques/critique-2026-11-04.md](critiques/critique-2026-11-04.md) (findings P1, P2 and P4). The PRD author may want to correct the same statements in the PRD comment.

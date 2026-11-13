# Alignment Check: spec.md against the source ask

## Source

The inline ask: "the issues described under 'These are the schema load, merge and rebase issues this work found or
fixed.'", which refers to the issue summary given in the same working session. That summary has four parts: seven
issues fixed by the work in progress, three behavior changes, six issues found but not fixed, and a verification
status. No URL was given.

## Verdict

⚠️ MINOR DRIFT (proceeding)

## Findings

| Severity | Category | Source reference | Spec reference | Description |
|---|---|---|---|---|
| Minor | added | "Found, not fixed": the proposed-change check still builds its candidate the old way | User story 4, FR-009 | The source lists this as not fixed; the spec fixes it in the first pull request. This follows from the source's own note that the proposed change's checks miss cases the merge refuses, and the critique did not object. |
| Minor | changed | "Found, not fixed": a branch schema load reads two views (unique and Number) | Issues table row 10, Out of Scope | The spec widens the list of merge-view checks to hierarchy and the relationship checks, verified on the current code. It stays out of scope, as in the source. |
| Minor | added | — | FR-012, critique P4 | Documentation of the new refusals and their recovery paths, added by the critique. It documents the source's first behavior change and adds no new behavior. |
| None | — | Fixed issues 1–7 | Issues table rows 1–7; user stories 1–3; FR-001–FR-008 | All present. |
| None | — | Behavior changes (rebase refusal, number pool scope check, proposed-change view) | Behavior Changes section | All present. |
| None | — | Regex, enum, length and choices (separate pull request) | User story 5, FR-010 | Present, as a second pull request. |
| None | — | The two unverified gaps | User story 6, FR-011 | Present, to be confirmed by tests first. |
| None | — | A refused proposed change stays refused until its checks run again | Edge Cases | Present, unchanged behavior. |
| None | — | Verification status (matrix results; R9 and R10 on `release-1.12` known by reading the code only) | Success criteria SC-001–SC-005; quickstart | The matrix is kept as the acceptance gate. The spec does not require rerunning R9 and R10 on `release-1.12` before the fix; the source recorded this as a gap in what was verified, not as a requirement. |

## Action

Proceed. No remediation pass was needed (0 of 2 used).

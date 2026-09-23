# Review passes

> Part of: `dev/guidelines/review/` | Related: [Repository Organization](../repository-organization.md)

Each pass reads the same diff for a different class of risk, one file per pass. A pass reports what
it finds and hands the decision back: none of them gates a merge.

| Pass | Reports |
| --- | --- |
| [Architectural review](architectural-review.md) | Risks the diff adds to the shape of the codebase: special cases that will be copied, files taking on a second job, imports pointing the wrong way |

Adding a pass: state what it reports and what it refuses to do, the signals with a threshold each,
and the shape of its report. Say which passes own the ground it does not cover, so two passes never
report the same finding.

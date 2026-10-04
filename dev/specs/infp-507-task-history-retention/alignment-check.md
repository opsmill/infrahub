# Spec/Ask Alignment Check

## Source

- [Notion design doc: Task history and Activity log retention](https://app.notion.com/p/opsmill/Task-history-and-Activity-log-retention-3dc228b830258012ba28dc3a23eece65), fetched through the Notion connector on 2026-10-04 at 10:23 UTC (the version that includes the Helm split, the 7-day activity log default, the reused `flush flow-runs` command with its rewrite option, and the two `[CLAUDE RECOMMENDED]` notes under part 1).
- The inline ask: grilling outcomes that fill gaps the page does not cover (startup validation of the settings, time windows anchored at the cursor, indicative timings), open items Q1, Q2 and deep time-paging, target release 1.13.

## Verdict

⚠️ MINOR DRIFT (proceeding)

Every behaviour row in section 2 and every decision D1 to D10 maps to a requirement, edge case or success criterion. The differences below are a code-verified correction, additions from the critique that implement the page's intent, and one softened timing that the user explicitly accepted as indicative.

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|---|---|---|---|---|
| Minor | changed | Section 2 "Page through the Activities page" (Today: the page asks for the total count); D7; Q2 | FR-025, Dependencies & Open Questions (Q2) | The Activities page's GraphQL query does not select `count` on `stable` or `develop`; the cost comes from the server counting on every request. The spec keeps "no count on the page" and the server-side fix, and marks Q2 as non-blocking. The design doc's "Today" column, D7 and Q2 should be corrected. |
| Minor | added | D9 ("existing command for old runs gets a new implementation") | Edge case "existing scripts keep working"; plan R5 | `--days-to-keep` kept as an override and `--batch-size` deprecated, so scripts that already clean task history keep working. Not on the page; added by the critique. |
| Minor | added | D9 (cleanup job), part 1 notes | Edge cases (concurrent Prefect cleanup, several replicas, locked table); plan R5 | One job across replicas (advisory lock), Prefect's delete order with retry on deadlock, a lock timeout on each rewrite. Not on the page; they make the page's cleanup safe now that Prefect's own cleanup runs at the same time. |
| Minor | added | D9 Helm paragraph ("the chart and the Helm guide leave the cleanup out") | FR-013; contracts/cli.md `--no-task-history-cleanup` | The page has no mechanism for the chart to leave the step out; from the second release on, the pre-upgrade hook reaches a task manager that provides the cleanup. The flag is documented for Helm only, so Compose still has no skip, as the page says. |
| Minor | added | — (grilling input) | FR-004 | Startup validation of the settings: from the inline ask, not on the page. |
| Minor | added | D5 | plan R2, contracts/configuration.md | `PREFECT_*` variables already set take precedence, with a warning. Not on the page. |
| Minor | changed | Section 2 "View the sub-activities" and "Filter branch merges ... by branch name" (under 0.1 s) | SC-005 (under 1 s) | Softened from 0.1 s to 1 s; the user accepted timings as indicative ("1 or 2 seconds is fine"). |
| Minor | missing | Section 4 follow-ups: new tickets for Helm persistent storage and the Postgres 14 to 18 move; private performance tests | — | Follow-ups outside this repository's scope; not requirements of this feature. Kept in the design doc. |

## Action

Proceed. No remediation pass. Report the first finding to the tech owner so that the design doc's section 2 "Page through" row, D7 and Q2 are corrected.

# PR lifecycle data model

Use typed records validated at API boundaries. All timestamps are aware UTC times from GitHub or
an injected clock; durations use calendar days with 24-hour UTC intervals. The ledger stores
compact policy state rather than copies of API response histories.

## PR snapshot

Repository and PR number/node ID; title/URL; author login/type; open/draft state; raw updated_at;
head SHA; base ref; current labels and assignees; requested users/teams; decisive reviews; check
state; mergeability/reviewDecision; paginated comment/review-comment/timeline observations; and
collection time/completeness. Snapshot fingerprint excludes attributable lifecycle writes only.

## Review state

For each reviewer, retain the latest decisive APPROVED/CHANGES_REQUESTED state with review ID/time
and dismissal information. COMMENTED does not itself revoke a decisive state. Unknown or incomplete
history cannot authorize removal of an exemption. Approval exemption and merge readiness are
separate booleans derived from complete state.

## PR ledger entry

| Field | Purpose |
| --- | --- |
| PR identity | Prevent accidental cross-repository/number reuse |
| activity_at | Last effective activity, independent of our own comments |
| observed_at, raw_updated_at | Baseline and reconciliation watermark |
| fingerprint | Detect persistent changes including head and body/title |
| external_digest, reopened_at | Detect complete-feed changes without retaining every historical event hash |
| warning | Optional cycle ID, comment ID, delivered_at, immutable deadline, sent milestone IDs |
| last_notice_at | Server delivery time and operation ID for seven-day rate limit |
| receipts | Compact comment/label identities needed to explain recent own writes |
| pending | Operation ID/type, prior-state hash, expected content hash, matching-feed baseline digest, and reconciliation state |

Fetch complete histories and hash the external feed after excluding exact authenticated receipts.
An aggregate change conservatively resets activity at observation time; a new reopening uses its
server time. Label intents retain a digest of matching pre-write events, so recovery must prove
exactly one added event. Do not retain full comment bodies or duplicate histories in the ledger. Missing/corrupt state requires conservative
recovery and cannot authorize closure from a label alone.

## Warning cycle transitions

- Eligible inactive → warning pending: publish initial notice only after 60-day threshold.
- Warning pending → warning active: server receipt and concrete deadline notice confirmed.
- Warning active → warning active: send an applicable 7-/1-day notice; preserve deadline.
- Warning active → canceled: observable activity, reopening, approval, or keep-open; neutralize
  the existing closure threat once and clear active warning metadata/display label.
- Warning active → due: deadline passed and current eligibility is still confirmed.
- Due → gated: attach current run/attempt capability after fresh checks.
- Gated → closed: independent API observation confirms the PR is closed after the stale pass.
- Gated → canceled/deferred: eligibility changes, incomplete data, failed close, or exhausted pass
  bound; remove the gate and record the reason. Deferred eligible cycles retain the deadline.
- Reopened → normal: reset activity from the reopening event; no inherited warning or gate.

An exempt PR can still receive ordinary reminders. Initial backlog and uncertain recovered cycles
must receive fresh warning notice; neither historical stale labels nor pending intents prove notice.

## Retention

Prune confirmed closed/merged entries only after owned gate cleanup and pending-write reconciliation.
Retain pending and active-cycle proof receipts plus compact feed digests for open PRs. After a
complete observation, retire confirmed ordinary receipts while preserving their delivery timestamp
and rebasing the external digest. Old comments remain recovery evidence. On reopening, reconstruct from the server event and start fresh.
Never discard unresolved writes to fit the issue-size cap.

## Dashboard and run report

One issue identified by stable machine marker and verified repository. If multiple matching issues
exist, fail with their identities rather than creating another. Visible rows have one primary
category and annotate secondary blockers/exemptions. Persist a versioned compact ledger after the
visible body; validate size and schema before writing. Ignore unsupported versions for mutation.

Run reports contain inventory count, complete classifications, notices proposed/delivered, warning
cycles, gate candidates, independently confirmed closed/open states, deferred reasons, API budget,
cache IDs/timestamps, completed passes, and last successful refresh time. Separate observed facts
from attempted operations. No successful timestamp is advanced on partial failure.

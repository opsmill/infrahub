# Alignment check: spec against the Jira task and the design document

Superseded in part: spec decision 8 (2026-11-17) makes the schema load and the schema check save the processed schema of the file without the applier, so the bullet on "its use by the schema load ... and the schema check" no longer holds; only the dropdown and enum mutations and the tests use the applier.

**Date**: 2026-11-14

## Source

- [IFC-3614](https://opsmill.atlassian.net/browse/IFC-3614): the description of the task (context,
  scope, acceptance criteria, risks), read through the Atlassian connector.
- [INFP-719 Make schema migrations visible](https://app.notion.com/p/opsmill/INFP-719-Make-schema-migrations-visible-402228b830258193b43ed097d965f633),
  as last edited on 2026-11-13, read through the Notion connector. Both pages need a login, so
  they were not read with a web fetch. The requirements compared are those of section "B: stored
  schema changes and migrations". The sections "Terms used in this document", "Assumptions" and
  "Out of scope", and the sections of the projects that depend on B, were read for the limits of
  B.

The spec compared is [spec.md](spec.md) after the critique fixes, at commit `ea8ef23685`.

## Verdict

⚠️ MINOR DRIFT (proceeding)

Every scope item, every acceptance criterion and every exclusion of the task is in the spec. The
six findings below differ from the sources. Each one is a decision that the spec states with its
reason, and none removes or reverses a requirement.

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
| --- | --- | --- | --- | --- |
| Minor | changed | Design B, "Schema change": a load "or a dropdown or enum mutation" creates its schema change with the status `running` before its migrations run | FR-006, FR-060, decision 7 | A dropdown or enum mutation stores its schema change as `applied`, in the transaction that saves the schema. These mutations run no migration, so no client can observe the status `running`. The load follows the source. |
| Minor | changed | Jira acceptance criterion: "A failed load is stored with the status `failed`" | FR-060, edge case, decision 1 | The spec stores a failed schema change when the load fails after its application started. A load that is refused before any write (an invalid file, a constraint that nodes fail) stores nothing. The source does not say whether a refused load is a failed load; the design creates the record "before its migrations run". |
| Minor | changed | Jira acceptance criterion: "Where today's load has a known bug, the expected result is the fixed behaviour" | FR-025, decision 2 | The expected result is the fixed behaviour, as the source says. A case whose bug is still open is marked as an expected failure. The four bugs are separate tickets with the status Draft. |
| Minor | added | Jira scope: a GraphQL query "following the `Preference` query". The source does not say who can read the history | FR-073, decision 3 | The query needs a logged-in account. The staging project of the design gives readers of the schema, anonymous ones included, access to a staged schema change. The history holds the error text of failed loads, and the constitution does not allow internal error detail for an anonymous reader. |
| Minor | added | Jira task [IFC-3619](https://opsmill.atlassian.net/browse/IFC-3619) (project C1): "The flow receives each migration result as it completes and updates the status and result in that migration's record" | FR-052 | The spec updates each migration record when its migration ends. The source for B asks that B "updates their status"; the timing is in C1's scope. The plan writes the record in the flow because the flow is the only place that receives each result. IFC-3619 then adds only the counts and the progress artifact. |
| Minor | added | Not in the sources | FR-072, FR-005, decisions 4, 5 and 6 | Details the sources leave open: a maximum page size, the definition of the time a schema change was applied, the parent of a branch's first schema change, the query returning the queried branch's own schema changes, and the status `rolled back` for the migrations of a failed load. Each is a clarification needed to make the requirement testable. |

Checked and found aligned:

- The four records and their fields, including the name `<version>_<summary>`, the parent, the
  branch, the four statuses of a schema change, the five statuses of an application, the five
  statuses of a migration record, and the format version.
- Operations named by kind and name, never by vertex ID, with the value before each property
  change, without `id` and `parameters.number_pool_id`, and without the paths that processing
  produces.
- The applier's three steps, and its use by the schema load, the dropdown and enum mutations and
  the schema check.
- The equivalence test suite as the first task, with every case of the design document.
- "Loading the same file twice stores one schema change."
- The query order: applied schema changes by version, failed ones by the time they were created.
- Deleting a branch deletes its schema changes, applications and migrations.
- Storage as internal records linked by edges, not a core kind. The spec does not name
  `StandardNode`; [plan.md](plan.md) and [data-model.md](data-model.md) do.
- No fingerprint. Failed loads on main kept with no automatic deletion.
- Out of scope: the upgrade migration, the replay at rebase and merge, staging, progress counts,
  node counts, the core schema update, front-end work, SDK and CLI commands.

## Action

Proceed. No phase is run again. Remediation passes used: 0.

The decisions behind the first four findings and the last one are listed in the spec under
"Decisions Taken During Specification" for a reviewer to accept or reverse. The fifth finding
touches the scope of IFC-3619, so its owner may want to remove the bullet about the flow from that
task.

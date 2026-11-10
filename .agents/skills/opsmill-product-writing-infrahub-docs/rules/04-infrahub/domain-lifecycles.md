# Domain lifecycles

Infrahub features have lifecycles. A page about one operation in a domain is usually wrong about the
others by omission, because the reader's next question is what happens to their work when the object
moves through the rest of its life.

**This rule is Infrahub-specific.** The principle behind it is not: in any repo, ask which operations
a domain supports before deciding a page's scope.

## Why this is its own rule

A how-to page for querying historical data covered reading data at a timestamp and comparing two
timestamps. It said nothing about what merging a branch does to history, which is the most surprising
behaviour in the domain: merged changes are recorded on the default branch at the merge timestamp,
not the timestamps they had on the branch, so the default branch holds a branch's result and not the
sequence that produced it. A reviewer caught it. The gap was not a wrong claim, it was a question
nobody asked, and no amount of verifying the claims on the page would have surfaced it.

Reading the page against its domain's operations would have.

## Operations per domain

Verify against the code before relying on any row. Each row lists where to look rather than asserting
behaviour, and the last column says whether the row has been checked against the code or only
written from familiarity with Infrahub.

| Domain | Operations | Where to check | Verified |
| --- | --- | --- | --- |
| Branches | create, read at a timestamp, merge, rebase, delete | `core/branch/models.py`, `core/diff/merger/merger.py`, `core/query/branch.py`, `branch/query_time_validator.py` | Against the code, 2026-09-04 |
| Proposed Changes | create, update, delete, review, run checks, merge, revoke approval | `graphql/mutations/proposed_change.py`, registered in `graphql/schema.py` | Not yet — written from familiarity |
| Artifacts | define, generate, check | `graphql/mutations/artifact_definition.py`, `workflows/catalogue.py` | Not yet — `regenerate` removed after a code search, the rest unverified |
| Schema | load, check, apply migrations | `workflows/catalogue.py` (`schema_apply_migrations`) | Not yet — written from familiarity |
| Resource pools | define pool, allocate a resource | `graphql/mutations/resource_manager.py` | Not yet — `release` removed after a code search, the rest unverified |

## Two operations that do not exist

Both were assumed while drafting this table, and both turned out to be inventions. They are recorded
because they are the kind of plausible-sounding operation that reaches a page unchallenged.

**Resource pools have no release operation.** Pools are defined and resources are allocated
(`IPPrefixPoolGetResource`, `IPAddressPoolGetResource`). Searching the backend for a release or
deallocate returns only distributed lock code in `lock.py`, which is unrelated. Do not write that a
reader can release an allocation until somebody establishes how one is actually freed.

**Artifacts have no regenerate operation.** Regeneration is a real concept — `refresh_artifacts` on a
Proposed Change causes artifacts to be generated again — but it is `generate` running a second time,
not a distinct operation with its own entry point. A page describing "regenerate" as a thing a reader
invokes would be describing an API that does not exist.

The lesson is the table itself. The branches row was verified by doing the work; the other four were
written from general familiarity with Infrahub, and two of those four named operations that do not
exist. A domain checklist is only useful if each row is verified, and the
plausibility of an operation is not evidence that it exists.

## How to use this

When a page covers one operation in a domain, work through the other operations in that row and ask
whether each one changes what the page claims. Where it does, either cover it or say plainly that it
is out of scope. Where the domain is not in the table, build the row from the code first — the
mutation module, the workflow catalogue, and the relevant query classes.

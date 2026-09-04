# Immutable History: the plan for documenting historical queries

## What this document is

This document records how the Immutable History documentation was planned and written, which facts
were checked against the source code, and which questions are still unanswered.

It exists so that a person who did not write these pages can understand why they are shaped the way
they are, and so that a future change to them does not repeat work that has already been done.

The pages it describes are:

- `docs/docs/immutable-history/overview.mdx` — explains the capability. This page already existed
  and was rewritten.
- `docs/docs/immutable-history/query-historical-data.mdx` — explains how to query historical data.
  This page is new.
- `docs/sidebars.ts` — changed so that Immutable History became a section in the navigation menu,
  with the overview page as its front page, instead of a single page.

The work was delivered as pull request 10334: <https://github.com/opsmill/infrahub/pull/10334>

The starting point for the work was an assessment of the company blog post about the temporal graph,
which is recorded in `temporal-graph-blog-assessment.md` in this same folder. The blog post was used
only to help decide how to frame the explanation. No sentence from the blog post was copied into the
documentation.

## Decisions that were taken before writing

**A separate page about the "temporal graph" concept was not created.** The vocabulary used in the
documentation stays as "immutable history" and "temporal queries". Existing pages were not renamed.
The term "temporal graph" appears once on the overview page, as a definition, because it is a useful
name for the storage design. It is not used as a heading or a page title.

**The Python SDK does expose the `at` parameter.** This was confirmed in the code, so the overview
page's claim that four interfaces support historical queries is correct.

**The blog post's performance claim was excluded.** The blog states that Infrahub supports hundreds
of branches with no performance penalty. Nothing in the repository supports that claim, so it does
not appear in the documentation.

**Comparing two arbitrary moments in time is a real capability, and it is in scope.** It works
through the GraphQL interface. It is documented on the new page.

## Where the page sits in the documentation, and why

The Infrahub documentation groups pages into sections. The section called "Branches and Change
Control" owns anything about branching, proposing changes, and validating changes. Immutable History
was already the first entry in that section, as a single page.

The Diátaxis model, which this documentation follows, separates pages into four kinds: explanation,
how-to guides, tutorials, and reference. Before this work, Immutable History had an explanation page
and nothing else. The missing kind was the how-to guide, which is what the new page provides.

The pattern used is a front page with pages beneath it. The existing overview page became the front
page, and the new page is the first page beneath it. This pattern is normally reserved for sections
that will hold several pages. It was justified here because a second page is plausible; see "What was
deliberately left out" at the end of this document.

No changes were needed in any other repository. The `at` parameter belongs to the platform, so the
main Infrahub repository is the correct home for the page. The Python SDK's own documentation may
eventually want a link to it, but that would be a separate change.

## Facts that were verified in the source code

Everything in this section was read from the code in this repository rather than taken from the
previous version of the page or from the blog post. Each entry gives the file and line so that it can
be checked again when the code changes.

### How each interface accepts a timestamp

| Interface | How the timestamp is given | Where this is in the code |
|---|---|---|
| Web interface | A time selector next to the branch selector. It shows only an icon until a time is chosen; afterwards a bar displays "Current view time" with the chosen value, and a cross clears it. | `frontend/app/src/entities/navigation/ui/time-selector.tsx`, lines 44, 73, 83 |
| GraphQL | A parameter named `at` in the address of the endpoint, written as `/graphql/<branch>?at=<time>` | `backend/infrahub/graphql/app.py`, line 206 |
| REST | A parameter named `at`, described in the code itself as accepting "absolute or relative format" | `backend/infrahub/api/dependencies.py`, line 81 |
| Python SDK | An argument named `at` on the methods `all()`, `get()`, `filters()` and `execute_graphql()` | `python_sdk/infrahub_sdk/client.py`, lines 277, 883, 1184, 2134 |

### Which time formats are accepted

These are read from `python_sdk/infrahub_sdk/timestamp.py`, lines 52 to 101. Infrahub tries them in
this order:

- A full date and time in ISO 8601 format, with a time zone or an offset.
- A date and time with no time zone, which is assumed to be UTC.
- **A date on its own**, such as `2026-03-09`. This resolves to **twelve o'clock midday UTC** on
  that day, not midnight. This is stated on the page because it surprises people.
- **A relative offset**, subtracted from the current time. Only three units are supported: seconds,
  minutes, and hours. They can be combined, for example `2h30m`. **Days and weeks are not
  supported**: writing `7d` produces an error. The unit definitions are at lines 22 to 26.
- Anything else produces an error called `TimestampFormatError`, at line 101.

### How far back a query can reach

This is in `backend/infrahub/branch/query_time_validator.py`, lines 24 to 32.

Only the earliest time is checked. The requested time must not be earlier than the effective
creation time of the branch. For any branch that is not the default branch, the effective creation
time is the creation time of the **default** branch, not of the branch itself. This is because
`origin_branch` always refers to the default branch.

The error message the reader will see is:

```text
Requested time '<time>' is before branch '<name>' was created at '<created_at>'.
```

**Nothing checks whether the requested time is in the future.** A future time is accepted, and the
query returns current data with no indication that this happened. The reason is that the filter used
to select versions is `from <= $at AND (to IS NULL OR to > $at)`, in
`backend/infrahub/core/timestamp.py`, lines 23 to 24, and every currently valid version satisfies
that condition for a future time. The web interface is not affected, because its picker only offers
times in the past (`time-selector.tsx`, lines 56 to 57). This affects GraphQL, REST, and the SDK.
See open item 2.

### How comparing two moments in time works

Comparing two moments requires two steps, and this was not understood correctly when the page was
first written.

First, a request called `DiffUpdate` asks Infrahub to calculate the difference and store it. Its
input accepts `branch`, which is required, plus optional `name`, `from_time` and `to_time`. There is
also a separate `wait_until_completion` argument, which makes the request return only once the
calculation has finished instead of starting a background task. This is in
`backend/infrahub/graphql/mutations/diff.py`, lines 24 to 36.

**If a custom period of time is requested, a name must also be given.** Without a name, Infrahub
refuses the request with the message "diff with specified time range requires a name". This is at
line 59 of the same file. This was not documented anywhere before, and it is the real reason why
asking for an arbitrary period appeared to return nothing on the first attempt.

Second, the stored result is read using either `DiffTree`, which returns the changed objects, or
`DiffTreeSummary`, which returns only counts. Their arguments are defined in
`backend/infrahub/graphql/queries/diff/tree.py`, lines 752 to 777:

- `name`, `branch`, `from_time`, `to_time`
- `filters`, which accepts `ids`, `status`, `kind` and `namespace`. The `status`, `kind` and
  `namespace` filters each accept lists named `includes` and `excludes`.
- `limit` and `offset`, for reading results in pages. These are on `DiffTree` only.
- `proposed_change_id`, which reads the difference belonging to a Proposed Change instead.

When `from_time` is not given, the comparison starts at the point the branch diverged. When
`to_time` is not given, it runs to the present. These defaults are at lines 463 to 476.

The base of the comparison is always the default branch, at line 551. See open item 1, because a
reviewer is not certain this is working as intended.

### What happens to history when a branch is merged, rebased, or deleted

**Merging** records the merged changes on the default branch using the timestamp of the merge, not
the timestamps the changes originally had on the branch. Every merge operation is given one single
timestamp, in `backend/infrahub/core/diff/merger/merger.py`, lines 94 to 210, which receives it from
`backend/infrahub/core/merge/branch_merger.py`, line 197.

The practical consequence is worth stating plainly, and it is now on the overview page. If somebody
creates an object on a branch on Monday and the branch is merged on Friday, the default branch shows
that object as created on Friday. The history of the default branch therefore contains the final
result of the branch, but not the sequence of changes that produced it. Those intermediate versions
stay readable on the branch itself, for as long as the branch exists.

**Rebasing** moves the timestamps of changes made on a branch forward to the time of the rebase, in
`backend/infrahub/core/branch/models.py`, line 433. A change recorded on the branch before a rebase
can no longer be read at its original timestamp.

**Deleting a branch** permanently removes the data and history recorded on that branch. The query
deletes every edge belonging to the branch, and any vertex left with no edges at all, in
`backend/infrahub/core/query/branch.py`, line 89. This cannot be recovered.

### How the timestamp behaves in the web interface

**The time picker does not use UTC.** The date picker component receives no time zone setting, and
the applied time is displayed using a local-time format. This is in
`frontend/app/src/entities/navigation/ui/time-selector.tsx`, lines 42 to 58 and line 75. The
previous version of the page told readers to choose a time "in UTC", which was wrong and could put a
reader in Central European Time one or two hours away from the moment they intended.

**The selected time applies to more than object data, and less than the whole interface.** Thirty-
seven files read the shared value that holds the selected time, which is called `datetimeAtom`.
Among them are object data, relationships, IPAM, groups, profiles, permissions, search, the schema
(`entities/schema/ui/queries/load-schema.query.ts`) and the navigation menu
(`entities/navigation/ui/queries/get-menu.query.ts`). No file belonging to the diff, Proposed
Change, task or event screens reads it, which means those screens continue to show current data
while the header still displays "Current view time".

**Editing is not prevented while a past time is applied.** There is no protection anywhere in
`frontend/app/src/`. A deletion forwards the historical timestamp
(`entities/nodes/object/ui/queries/delete-object.mutation.ts`, lines 18 and 26) and the backend then
silently replaces it with the current time (`backend/infrahub/graphql/app.py`, line 223). No error
is shown. See open item 3.

**The selected time is part of the page address**, as a parameter named `at`
(`shared/config/qsp.ts`, line 5), and it is preserved as the reader moves around the interface,
alongside the branch (`shared/api/rest/fetch.ts`, line 83). This means a historical view can be
saved as a bookmark or shared as a link.

### The schema is also resolved for the requested time

When the requested time is earlier than the moment the branch's schema last changed, Infrahub loads
the schema as it was at that time and analyses the query against that older schema. This is in
`backend/infrahub/graphql/app.py`, lines 228 to 231. A query for an earlier time therefore sees the
attributes that the schema defined then, rather than the ones it defines now.

### A timestamp applies to reading only

If a query document contains a change as well as a read, Infrahub replaces the requested timestamp
with the current time, in `backend/infrahub/graphql/app.py`, line 223.

### There is a third way to ask about the past

Besides reading one moment and comparing two moments, there is a third operation: asking which
events happened between two moments. The event query accepts filters named `since` and `until`,
along with `branches`, `account__ids`, `event_type` and node identifiers. `since` defaults to one
hundred and eighty days in the past and `until` defaults to the current time. This is in
`backend/infrahub/graphql/queries/event.py`, lines 48 and 140 to 143.

This is why the new page opens by naming three ways to ask about the past rather than two. See open
item 4, because these filters are not documented on any page.

## How a comparable product documents this, and what that changed

The equivalent page from Dolt, a database with similar version-control behaviour, was used as a
benchmark: <https://www.dolthub.com/docs/sql-reference/version-control/querying-history>

Dolt's page leads with the constraint before it shows any syntax. It states that the unit of a
snapshot is the commit, then works through each interface, then closes with an explicit list of
limitations.

This changed one thing in the plan. The section describing constraints was moved **above** the
per-interface syntax rather than being left as a footnote at the end. The reasoning is that a reader
whose first historical query fails will have failed for one of two reasons — the branch boundary, or
an unsupported time unit — and both of those belong before the examples rather than after them.

## What changed during the writing, because the code contradicted the plan

**REST has no general way to read an object at a past time.** The `at` parameter is accepted only on
`/api/query/{query_id}`, `/api/artifact/{artifact_id}`, and the two transformation endpoints
`/api/transform/python/{transform_id}` and `/api/transform/jinja2/{transform_id}`. This is in
`backend/infrahub/api/dependencies.py`, lines 77 to 90, and
`backend/infrahub/api/transformation.py`, lines 35 and 100. The section describing REST therefore
explains saving a read as a stored query and running that, instead of describing an ad-hoc object
read that does not exist.

**`DiffTree` reads a stored result rather than calculating one.** This is described above. The page
was originally written as though `DiffTree` performed the comparison itself.

**The getting-started tutorials are not published.** The folder
`docs/docs/tutorials/getting-started/` is excluded from the documentation build, in
`docs/docusaurus.config.ts`, line 83. This was discovered when the build failed after a link was
added to the existing tutorial about historical data. That whole tutorial series is unpublished. See
"What was deliberately left out".

**Two structural changes were made.** The four interfaces became four tabs within one section rather
than four separate sections, following the pattern already used in `docs/docs/groups/create.mdx`.
And a use case about testing automation against historical data was left out of the introduction
entirely, rather than written and marked as unconfirmed, because nothing in the repository supported
it.

**Both pages are written with one paragraph on one line.** They were originally broken across
several lines at roughly one hundred characters. A reviewer asked for this to change. It is the
correct choice, because the line-length rule is switched off in `.markdownlint-cli2.yaml`, and
neighbouring pages such as `docs/docs/branches/overview.mdx` are written as single long lines.

## Open items

These are grouped by who can decide them. None of these are writing problems. Each needs a decision
or a confirmation from a person.

Each item below states the question and who can answer it. A handover comment on pull request 10334
covers the same items in more depth. For each one it sets out the available options with their
trade-offs, how the item could be checked, and what to do with each possible answer. That comment
stays readable on the pull request after it is merged. Read it alongside this section rather than
instead of it: this document records why the pages are shaped as they are, and the comment records
what to do next.

### Items that need an engineer

**Open item 1. Is the base of the comparison in `DiffTree` working correctly?**

The page states that the base of a comparison is always the default branch, which is what the code
does at `backend/infrahub/graphql/queries/diff/tree.py`, line 551. However, a reviewer commented
that he was not certain this is working as intended. Documentation should not describe behaviour that
nobody is willing to confirm. Please have an engineer confirm it. If the behaviour is wrong, remove
that sentence from the page and raise a bug report instead.

**Open item 2. Is it intended that a future timestamp is accepted?**

As described above, only the earliest time is checked. A time in the future is accepted and returns
current data silently.

The page currently documents this as normal behaviour. That may be the wrong choice. If engineering
would prefer future timestamps to be rejected in the same way that too-early timestamps are
rejected, then the paragraph describing it should be deleted from the page, and this should become a
bug report instead.

### An item that needs a product decision

**Open item 3. Should the page warn about editing in a past view, or should the behaviour be fixed?**

As described above, nothing prevents somebody from editing or deleting data while they are viewing a
past moment, and the change is applied to current data.

There is history here. GitHub issue 2268 asked for exactly this protection in February 2024 and was
closed in March of that year, but no protection exists in the current code.

The page currently carries a warning box. That was a deliberate choice: it seemed better to warn
people than to let them discover the problem by losing data. But warning about a problem is not the
same as fixing it, and this is a product decision rather than a documentation one. If the behaviour
is fixed, the warning box should be removed.

### Items that need a decision about scope

**Open item 4. The `since` and `until` filters are not documented anywhere.**

The new page opens by naming three ways to ask about the past. The third is the event query with its
`since` and `until` filters. The table links to the Activity log page, because that is the closest
existing page, but that page only describes the filters available in the web interface. It does not
describe the query parameters, and it does not mention that `since` defaults to one hundred and
eighty days in the past.

There are two reasonable options: extend the Activity log page as a separate change, or add a short
section to the new page. This was not decided, because either choice changes the scope of this work.

**Open item 5. A reviewer suggested a diagram.**

On the subject of how merging and deleting affect history, a reviewer wrote that a graphic would
explain the concepts much better. The written explanation now exists. A diagram would probably
communicate it more clearly, and would need somebody who produces diagrams for the documentation.

### Statements a reviewer asserted that were not confirmed in the code

Both statements are now on the pages. Both came from a maintainer, so they are very likely correct.
Neither was confirmed by reading the code, so both should be checked before merging.

**Open item 6.** The page says that after a branch is deleted, the Activity log still records the
operations that were performed on that branch. Events are stored separately from the graph data, so
this is plausible, but it was not confirmed that the query which deletes a branch's data leaves the
events untouched.

**Open item 7.** The page describes the creation time of the default branch as the point at which
Infrahub was first initialised. That phrasing came from the reviewer. The code only states that the
limit is the creation timestamp of the default branch. The explanation helps the reader, but it
should be confirmed.

### An item that was in the original plan and is still open

**Open item 8. Is `updated_by` the right way to answer "who changed this"?**

The overview page says that a change can be traced to the account that made it, and links to
`docs/docs/objects/metadata.mdx`. Reading `updated_by` at a past timestamp gives the account behind
the change that was current at that time, which is why the claim stands. This should be confirmed as
the intended way to answer that question.

## What was deliberately left out

These are not oversights. They were considered and excluded on purpose.

**A second page about comparing two points in time.** This would cover `DiffTree` in depth alongside
the Proposed Change difference. The current page gives it one worked example. A full treatment needs
somebody to settle the relationship between comparisons based on timestamps and comparisons based on
branches, which is a larger question than this work.

**Any link to the getting-started tutorials**, because they are not published. Deciding what happens
to that tutorial series is separate work.

**The blog post's claim about performance**, because nothing in the repository supports it.

**A full review of the writing style across the rest of the overview page.** Only the sections
touched by this work were revised.

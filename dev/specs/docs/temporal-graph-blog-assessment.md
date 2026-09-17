# Assessment — "How to Time Travel on Your Network With a Temporal Graph"

Source: <https://opsmill.com/blog/temporal-graph-infrastructure-data/> (Damien Garros, 2026-03-09)

Status: complete. Every recommendation below was either carried out or deliberately rejected, and
every open question at the end has since been answered. Those answers are recorded in place, so this
document now serves as the record of why the Immutable History pages are shaped the way they are.
The work itself is described in `immutable-history-temporal-queries.md` in this same folder.

## Verdict

**Do not add the post as a docs page.** Its conceptual content is already covered in
three places in the docs, and it carries no technical substance to add. But reading it
against the docs exposes a real gap that is worth its own pull request: the docs claim
temporal queries work across four interfaces and never show how to run one.

Recommendation: use the post as **framing source material** for two changes — one new
how-to page, one edit to an existing concept page. Nothing from the post is imported as
prose.

## What the post contains

Nine short sections, all conceptual:

- the problem with only storing "now"
- what a temporal graph is (timestamps on nodes and relationships)
- temporal graph vs. change log
- the case for immutability (trustworthy record, cause and effect, safe parallel work)
- multiple timelines at once (branches share an immutable baseline, record only divergences)
- why it matters (query any point, test against historical state, precise rollback)
- how it shows up in Infrahub (attribute-level immutable values, lineage metadata,
  Git-like workflow at the data layer, diff between two points in time, time picker in the UI)

No API endpoints, no GraphQL parameters, no CLI commands, no schema or Neo4j detail, no
versions. Audience is prospects; the closing call to action is a demo request.

This is marketing material. It was written for prospective customers, not for engineers, so it was
used only to help decide how to frame the explanation. No sentence from it was copied into the
documentation.

## What the docs already cover

| Page | Covers | Quadrant |
|---|---|---|
| [`overview/concepts.mdx`](../../../docs/docs/overview/concepts.mdx) §"Immutable graph and historical data" | One paragraph — the engine is immutable, history is queryable | Orientation |
| [`immutable-history/overview.mdx`](../../../docs/docs/immutable-history/overview.mdx) | Benefits, use cases, timestamps and commits, temporal queries, attribute-level tracking | Concept |
| [`tutorials/getting-started/historical-data.mdx`](../../../docs/docs/tutorials/getting-started/historical-data.mdx) | Using the UI time selector to see a value before a merge | Tutorial |

Three of the post's nine sections restate what `immutable-history/overview.mdx` already
says, in some cases almost claim for claim. A fourth conceptual page would give the same
assertion a fourth place to drift.

## The gap the post exposes

`immutable-history/overview.mdx` states that temporal queries work through the Web UI,
the GraphQL API, the REST API, and the Python SDK. **The docs never show a temporal query
in any of them.** The only place the parameter appears is one bullet in an unrelated
tutorial:

- `learn/tutorials/transformations/build-a-jinja2-transformation.mdx:324` —
  `?branch=main&at=<time of your choice>`

Verified against the source, not the post:

- `at` is a query-string parameter on both the REST API and the GraphQL endpoint
  (`backend/infrahub/api/dependencies.py:81`, `backend/infrahub/graphql/app.py:206`).
- It accepts **absolute or relative** formats — the relative form is documented nowhere
  in the docs.
- Requests are validated per branch by `BranchQueryTimeValidator`
  (`backend/infrahub/api/dependencies.py:88`), so some time/branch combinations are
  rejected. That constraint is undocumented, and it is the kind of thing a reader hits
  on their first attempt.

The missing quadrant is how-to. The concept is over-served; the task is unserved.

## Recommended changes

### A. New how-to page — `docs/docs/immutable-history/query-historical-data.mdx`

Title: "Query historical data". Turns Immutable History from a single page into a small
hub with one spoke, following the hub-and-spokes pattern.

Content, all sourceable from the code and the existing UI:

- selecting a time in the UI (the existing tutorial screenshot can be reused)
- `at` on the GraphQL endpoint, with a worked query
- `at` on the REST API
- absolute vs. relative time formats
- what happens when a time predates the branch, and why

Sidebar: `sidebars.ts:241` becomes a category with `immutable-history/overview` as its
hub link.

### B. Edit — `immutable-history/overview.mdx`

Two framings the post articulates better than the current page, and that the page is
missing rather than duplicating:

1. **Temporal graph vs. change log.** The current page explains that history is kept.
   It never explains that state at every point in time is directly queryable rather than
   reconstructed from a log of operations. This is the distinction that tells a reader
   why the feature is different from an audit trail, and it is the post's strongest section.
2. **Multiple timelines at once.** Branches share an immutable baseline and record only
   divergences. The page currently lists "parallel workflows" as a benefit without saying
   what makes it cheap. This also connects the page to Branches, which it already links to.

Both were conceptual claims that needed confirming with engineering before being written. Both were
subsequently confirmed against the source code and are now on the page.

### C. Not recommended — a "Temporal graph" concept page

The docs' vocabulary for this is **immutable history** and **temporal queries**. The post
uses **temporal graph** and **multi-temporal graph**, which are positioning terms aimed at
a prospect audience. Introducing a third name for the same capability splits search, and
the reader now has to work out whether the three pages describe three things.

This is a terminology call rather than a docs-mechanics call, so it is yours to make. If
"temporal graph" is becoming the canonical product term, the right move is to rename
across the existing pages, not to add a page beside them.

## The open questions, and how each was answered

All four questions below were resolved during the work that followed. They are kept here with their
answers, because the answers explain decisions that are otherwise invisible in the finished pages.

**Question 1. Is "temporal graph" now the product term, or does it stay marketing vocabulary?**

Answered: it stays marketing vocabulary. The documentation continues to use "immutable history" and
"temporal queries". Recommendation C was therefore rejected, and no page was renamed. The term
"temporal graph" appears exactly once on the overview page, as a definition of the storage design,
because it is a useful name for that design.

**Question 2. Does the Python SDK expose `at`?**

Answered: yes. It is an argument on the methods `all()`, `get()`, `filters()` and
`execute_graphql()`, in `python_sdk/infrahub_sdk/client.py` at lines 277, 883, 1184 and 2134. The
overview page's claim that four interfaces support historical queries is therefore correct and
needed no correction.

**Question 3. Should the claim about hundreds of branches with no performance lag be repeated?**

Answered: no. Nothing in the repository supports it, and no benchmark was found to cite. It was left
out of both pages.

**Question 4. Is the difference between two arbitrary points in time genuinely available, or is it
only the Proposed Change difference between two branches?**

Answered: it is genuinely available for two arbitrary timestamps, through the GraphQL interface, and
it is documented on the new page. However, it works differently from how this document assumed. It
takes two steps rather than one: a request called `DiffUpdate` calculates the difference and stores
it, and only then can `DiffTree` or `DiffTreeSummary` read the result. A custom period of time also
requires a name, or the request is refused. The details are recorded in
`immutable-history-temporal-queries.md`.

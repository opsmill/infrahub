# Step 2.7 — Review comparable docs ★

## Contents

- [When to run](#when-to-run)
- [How to run it](#how-to-run-it)
- [When a blog is one of the inputs](#when-a-blog-is-one-of-the-inputs)
- [The accuracy guardrail](#the-accuracy-guardrail)

Read how comparable products in the **same class of feature** solved the same problem, check the facts against the code, and produce a gap list: what you can source and write accurately, and what only the feature's owner can answer. Both go to the outline gate.

**This is research, and it runs before the outline**, so that what you find shapes the plan. If you are reading another product's docs while drafting or reviewing, this step was skipped, and the page will need restructuring after it is written instead of being outlined correctly once.

Most inputs cover the mechanics — config keys, the API, the steps to turn something on — and say little about when someone would use the feature or how it compares to the alternatives. Closing that gap is what this step is for.

## When to run

- **New feature docs** — always. Highest risk of thin conceptual input.
- **A smaller update or improvement** — a lightweight pass scoped to the page being touched. Skip if the change is a pure mechanical fix (typo, renamed flag).
- **When a recommendations doc exists (Step 2.5)** — still run it. Step 2.5 checks the spec's *structure and placement*; this step checks its *content depth*. A well-placed spec can still be shallow.
- **When the page is a comparison or decision page** ("which of these do I use") — always, whatever the use case. External models transfer most directly on this shape; see [comparison-page](../03-patterns/comparison-page.md).

## How to run it

### 0. Code accuracy pass (new feature docs — required before drafting anything)

For new feature docs, **read the implementation before writing a single sentence.** The announcement, messaging brief, and spec describe intent — the code describes what shipped. These diverge more often than anyone expects.

For every source file relevant to the feature (backend resolvers, frontend form components, route definitions, permission checks, config), read and extract:

- **Every UI label** — field names, button text, tab titles, menu items, section headers. The code is the ground truth: verify every label in the component that renders it.
- **Every API argument** — name, type, required/optional, default, max/min. Extract from the input type definition, not from the spec.
- **All entry points** — every place in the UI that can open or seed the feature (dedicated nav item, object Actions menu, right-click context menu, deep-link URL parameters).
- **Permission and security behaviour** — how access control is applied; whether it is per-object, per-kind, per-role, etc.
- **Defaults and limits** — take the exact values from the code, which may have moved since the spec.
- **The rest of the domain's lifecycle** — a page covering one operation is usually wrong about the others by omission. Work through the operations for the domain in [domain-lifecycles](../04-infrahub/domain-lifecycles.md) and ask whether each one changes what the page will claim. A how-to on querying historical data shipped for review without saying what merging does to history, which is the most surprising behaviour in the domain; that was a question nobody asked, and verifying the page's own claims would never have surfaced it. Where the domain is not in that table, build its row from the mutation module, the workflow catalogue and the query classes before the outline.
- **Discrepancies between announcement and implementation** — where the spec or announcement says X and the code says Y, flag it explicitly. Do not silently use one over the other. Surface it as an open issue for the SME.
- **Canonical name vs. UI label** — the feature may be marketed under one name ("Graph Traversal") but displayed differently in the UI ("Path Traversal" in the tab title and side panel). Extract the literal string used in every UI surface: page header, tab title, sidebar menu item, route path, Actions menu entry. If the docs section title, sidebar category, or PR branch name differs from the literal UI label, add a one-line note in the overview ("In the UI, this feature is labeled **Path Traversal**") and flag it as an open issue. A reader who reads the docs title then scans the left nav for that name will be confused if the two don't match.

This pass is required, not optional, and must happen **before** the outline gate. The outline must be built on verified facts. Finding a discrepancy after drafting is expensive; finding it here is free.

**What to do with findings:**

- Features present in code but absent from the planned outline → add to the outline.
- Facts that differ from the spec → use the code value; flag the discrepancy as an open issue for the PR.
- Behaviour that is more nuanced than the spec implies (e.g. permission filtering is per-*kind*, not per-object) → document the accurate behaviour; note the source file and line.

### 1. Name the feature class

Identify what kind of feature this is — the class sets the bar for what "good" looks like:

| Feature class | Comparable OSS docs to benchmark against |
|---|---|
| Authentication / SSO / directory | GitLab, Grafana, Authelia, HashiCorp Vault, Keycloak |
| IPAM / DCIM / source of truth | NetBox, Nautobot, phpIPAM |
| Data sync / ETL / integration | Airbyte, Meltano, Fivetran |
| CLI tooling | uv, `gh`, Stripe CLI |
| API surface | Stripe, FastAPI |
| Observability / events | Prometheus, Grafana |

The list is a starting point — pick 2–4 docs for the actual class, favoring docs technical readers respect.

### 2. Read how the comparables frame it

For each comparable, note what conceptual sections it includes that the current inputs don't cover. Use this checklist as the bar — it is the [overview page content model](../03-patterns/overview-page-content.md) plus the operational layers:

- **What it is** — a one-paragraph capability lead.
- **Why you would use it** — the situation that makes the capability relevant, described concretely. This is the section most often absent from the inputs, and the one you cannot read off the code; if no source supplies it, it becomes a question, not invented prose.
- **When the capability is relevant** — concrete situations, not a list of conditions that excludes nobody.
- **How to choose among the alternatives** — where more than one mechanism reaches a similar result. A decision table when the feature is one of several interchangeable options. See [overview-page-content](../03-patterns/overview-page-content.md) and, for pages built around the comparison, [comparison-page](../03-patterns/comparison-page.md).
- **Boundaries, or where another mechanism fits better** — only where it materially helps the decision.
- **Prerequisites.**
- **Best practices / recommended configuration** — the production-ready setup, not just the minimal one.
- **Operational "when it matters" context** — security, performance, lifecycle (provisioning *and* deprovisioning), failure modes, limits.
- **Troubleshooting.**
- **Examples grounded in real values.**

### 2.5 Read the other product's docs before describing it

When the page describes or references a capability of **another product or satellite** (Infrahub Sync, the Python SDK, an integration), read that product's own docs before writing a sentence about it — don't paraphrase from memory or from how the current page already describes it. Real example: a page described Infrahub Sync as one-way import ("import from an external system such as NetBox"); the Sync docs say it is bidirectional and also publishes Infrahub data outward. The one-line summary was the only thing anyone had checked it against, so the error survived review. Reading the other product's introduction page takes a minute. Describing another team's product incorrectly is much more costly to fix.

### 2.7 Ask what else in Infrahub a reader might choose instead

Comparable products tell you what a page of this kind usually covers. They do not tell you which
Infrahub mechanism a reader will confuse this one with, and that is often the more useful question.

Ask: **what adjacent Infrahub feature could a reader reasonably consider for the same job?** Then
research the distinction and source it.

Real cases: a computed attribute against `display_label` against `human_friendly_id`; a Generator
against a Transformation; a Profile against an Object Template; a historical query against the
activity log. In each, more than one mechanism turns modeled data into something a reader wants, and
nothing in the docs says which to reach for.

Add the distinction to the page where getting it wrong changes the implementation. Do not add a
comparison section merely because related features exist.

### 3. Classify every gap

A gap is **sourceable** when you can back the answer with an authoritative source — the code, the repo, the spec, or the messaging brief — and therefore write it accurately without guessing. Sort each missing piece by that test:

- **Sourceable → propose it.** You can confirm the answer from code, repo, spec, or brief, so draft the concrete improvement and propose it. Examples from the LDAP review: "add a local-vs-LDAP-vs-SSO decision table"; "state the LDAPS-vs-STARTTLS rule and that the two are mutually exclusive" — both confirmed in `config.py`, so they could be written accurately.
- **Not sourceable → ask, don't write.** The answer isn't in any source; it lives in someone's head (the PM's, the engineer's). Examples: "when should a team choose this over X?", "what's the recommended production configuration?", "what are the best practices?". List these as explicit questions for the user to answer — or to confirm the topic is intentionally out of scope. Do not draft the prose yourself, however plausible it sounds.

## When a blog is one of the inputs

A product or technical blog is often the best statement of why a capability exists, and it is
written to a different brief. Take the parts that explain the product; leave the argument.

**Bring it into the docs when it clarifies:**

- what Infrahub does;
- when the capability is useful;
- how the capability behaves;
- which operation or interface to choose;
- a mental model the feature needs;
- a limit or edge case;
- how the capability differs from a neighboring Infrahub concept.

**Check whether the blog is built around one application of a broader feature.** If it is, work out
the general capability before you build the page's examples, or the blog's strongest use case becomes
the definition of the feature. The naming-conventions post is entirely about names and descriptions;
computed attributes are any `Text` or `URL` value calculated from modeled data, and a page drawn
straight from that post reads as though naming is what the feature is for.

Four questions before drafting from a source like that: what is the general capability; what makes
the source's example an example of it; what other examples show its breadth; and which parts are
specific to that story and should stay in it.

**Leave the fuller treatment in the blog when it is mainly:** a broader architectural argument,
industry commentary, thought leadership, an extended comparison with alternative approaches, product
philosophy, or a narrative explanation. Link to it for readers who want that.

**Worked example.** The temporal-graph blog draws a distinction that belongs in the docs: an activity
log records the operations that happened, while immutable history lets you query the values and
relationships those operations produced, at a timestamp. That tells a reader which capability to use
for which question. The same blog's argument about temporal databases changing network automation
does not, and stayed in the blog.

**Two things to watch.** Product claims in a blog are marketing copy until verified — the
performance claim in that post was left out because nothing in the repository supported it. And a
correction to one claim does not invalidate the source: being told to drop that performance claim is
not instruction to stop using the blog, and treating it that way cost a full rewrite. Material the
user handed you stays validated input, including its problem and value sections.

## The accuracy guardrail

**Do not present unsourced overview, when-to-use, best-practices, or "when it matters" content as established fact.** What the guardrail forbids is passing judgment off as sourced fact — not the judgment itself.

Where a source establishes the situation but not the sentence, reason from it and write the content, marked as a recommendation the reviewer can confirm or correct. A labelled recommendation is more useful than an omission; an unlabelled invention is worse than either. Product behaviour is the exception and stays strict: versions, defaults, limits, flags, and API arguments come from the code or the docs, never from reasoning.

Orientation pages carry more reasoned content than reference pages do, by design — explaining why a capability matters is their job. See [explain-and-describe](../01-principles/explain-and-describe.md).

**Material the user gave you is validated input.** Messaging briefs, discovery docs, transcripts, survey pages, and plans handed over at Step 0 are sources — all of them, including their problem, alternatives, and value sections, not only their capability lists.

**Anything the user approved is validated input, including your own recommendations.** This covers more than documents they wrote:

- An outline or plan approved at a gate is approved content. You have the sign-off to write what it says each section contains, and do not need per-sentence approval on top of it.
- A recommendation you made and the user accepted — a structure, a framing, a decision between options, a naming rule — is settled. Write it as content.
- Research you carried out and presented, once the user accepts it, is part of the corpus. If they asked "how do other sites handle this, what do you recommend" and approved the answer, the findings and the recommendation are both usable material, not speculation to be re-flagged.

Approval is often informal — "yes, let's do that" is approval. Once given, do not re-label the content as tentative, re-open the decision, or hedge it in the draft. Product behaviour is the one thing approval cannot settle: a user agreeing to a claim about a default or a limit does not make it true, and that still gets verified against the code or the docs.

**Draft from the sources, not from your summary of them.** The plan you produced at Step 3 is an index of the material, not a replacement for it — it is deliberately compact, and everything it leaves out is still needed at drafting time. Before writing each section, re-open the specific sources that section maps to (Step 3 records that mapping) and work from them.

Two failure modes this prevents. The situation material — "current state and pain points", "alternatives", "why teams struggle today" — lives in sections that a capability-focused reading skips, so it never reaches the plan and therefore never reaches the page. And the plan states conclusions where the source has the reasoning, examples, and specifics behind them; a draft written from conclusions alone reads as a list of assertions, because that is what it was built from.

**SME-authored content is a valid source.** Existing content written by a colleague with domain ownership — a "use when" column an engineer wrote in the PR being improved, an SME's paragraph in a review comment — counts as validated input, the same tier as a spec. Don't flag it as invented content needing sign-off, and don't discard it because it's terse. Preserve its *substance*; its phrasing still goes through the voice rules like any other source. When you extend it — adding when-to-use context the SME didn't write — label your additions as recommendations for the SME to confirm, separately from their validated claims.

The guardrail can also be **explicitly overridden by the user** ("I'm asking you for the when-to-use guidance — write it"). Honor the override, and record it where a reviewer will see it (plan file, PR description), so judgment-sourced prose is visible as such rather than passing as sourced fact.

★ **Gate**: present three things — (a) the comparable docs you benchmarked against, (b) the improvements you can source, drafted as concrete proposals, and (c) the missing-input questions. The user picks which proposals to adopt and answers or waives the questions. Their decisions feed the outline at [Step 3](step-3-outline.md). Do not draft conceptual content the user hasn't supplied or approved.

**If a missing-input question goes unanswered** — the user doesn't have the answer, defers it, or the question is still open when the PR is created — **do not silently drop it.** Convert it to a named open issue and carry it forward to the PR description. Each open issue should state:

- What content is missing (e.g. "Best practices: depth tuning and when to use kind/relationship filters")
- What comparable docs include this (e.g. "NetBox graph traversal docs cover this in a dedicated section")
- A direct ask for the reviewer/SME: supply the content, or confirm it is intentionally out of scope for this release

This ensures nothing falls through the cracks between the audit and the merge. A PR reviewer who is the feature SME is the right person to resolve these — not to discover them after merge.

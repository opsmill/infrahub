# No customer or personal data in docs or PR bodies

**Never put customer-identifying or personal information into published docs, code samples, screenshots, commit messages, or the PR body.** Docs repos and their pull requests are public or broadly readable. Anything written there is permanent and indexable, including text later edited out of a PR description.

This applies to every use case and every repo. It is not negotiable and it is not a ★ gate you can pass by asking "is this okay?" mid-draft: strip it first, then raise it if the detail was load-bearing.

## What counts

This list governs **what ships**: the published docs, code samples, screenshots, commit messages, and the pull request body. It does not restrict what you may read, cite in your own working files, or discuss with the user. Working from a JPD card, checking a recommendations doc at [Step 2.5](../02-workflow/step-2.5-spec-review.md), publishing an outline to Notion for review, and linking sources in the outline's mapping are all normal and expected. The rule bites at the boundary where content leaves internal tooling for a public repository.

- **Customer and prospect names**, including the company, its subsidiaries, its product names, and any nickname or shorthand the team uses internally.
- **People**: names, job titles tied to an individual, email addresses, phone numbers, Slack or Jira or GitHub handles, meeting attendee lists.
- **Attributable quotes** from transcripts, calls, support threads, or Slack, even anonymized ones that a reader could trace back to an account.
- **Customer environment data**: real hostnames, device names, site codes, IP addresses, prefixes, ASNs, VLAN or VRF names, circuit IDs, serial numbers, API tokens, URLs of a customer's Infrahub instance.
- **Commercial context**: deal stage, pricing, contract terms, renewal dates, PoV scope, escalations, named support tickets.
- **Internal tracker references** that name a customer, *in shipped content*: Jira issue titles, Notion page names, JPD cards, KB entries under a customer slug. Reading these is the job; carrying their titles or links into a public file is not.

## What to write instead

Generalize to the pattern. The reader needs the shape of the problem, not who reported it.

| Instead of | Write |
|---|---|
| "Requested by <Customer> for their DC fabric rollout" | "For multi-site fabric rollouts" |
| "As <Person>, network architect at <Customer>, put it: ..." | Drop the quote; state the requirement in your own words |
| Real hostnames like `par-dc1-leaf07.customer.net` | `atl1-edge1`, `site1-leaf1`, or the docs' existing example naming |
| Real addressing | RFC 5737 IPv4 (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`), RFC 3849 IPv6 (`2001:db8::/32`), RFC 5398 ASNs (`64496`–`64511`) |
| Real domains and emails | `example.com`, `example.net` |
| "See <Customer> transcript in the KB" | Cite the fact, not the source; keep the internal link out of the PR |

Attribute internal input by role, not by person: "per the schema owner", not "per <Person>".

## Screenshots and diagrams

Screenshots carry data the prose does not. Before adding one, check the browser tab title, breadcrumb, account or org name, branch names, user avatar and menu, notification badges, and any object names in the table. Retake against demo data rather than redacting with a black box, since a box still shows the shape and length of what it hides.

## Where to check

- **Every new or modified doc file**, prose and code blocks alike.
- **The PR body** drafted at [Step 10](../02-workflow/step-10-pr-description.md), especially the "What needs reviewer attention" and "Open issues for the reviewer / SME" sections. Those are where sourcing context ("<Customer> asked for this", "flagged on the <Customer> call") leaks in.
- **Commit messages and the branch name.**
- **Inputs you carried in**: transcripts, KB entries, discovery briefs, and JPD cards are internal sources. Read them for facts, then leave the identifiers behind.

The [Step 9](../02-workflow/step-9-pre-pr-audit.md) pre-PR audit runs this as its own pass.

## When the customer identity is genuinely needed

Some content legitimately names a customer: a case study, a published quote, a logo, a reference architecture credited to an account. That content is not yours to approve.

Stop and ask the user. Named customer content ships only with the customer's written approval routed through marketing or the account owner. Do not include it on the assumption approval exists, and do not draft it in a PR body "so the reviewer can decide".

## Why

Docs PRs on `opsmill/infrahub` are public. A leaked customer name in a merged PR body is a support and legal problem that no later edit fully undoes: the commit, the PR event stream, email notifications, and any mirror or scraper keep the original text. Removing it before it lands is the only reliable control.

# Section-wide migration

When migrating multiple features in a single PR (a whole docs section like Branches & Change Control), apply these patterns on top of the standard workflow.

## One feature at a time, with build verification between each

Convert one feature at a time: convert → build → verify the pages render → move to the next.

For B&CC: do Branches first (hub + 4 spokes + verify), then Proposed Changes (hub + 3 spokes + verify), then Checks (hub only). Catches problems early instead of compounding them.

## Hub-after-extraction review

When a hub loses its H3 content to spokes, verify the hub still reads as a coherent concept page on its own — not a stub. Re-read the hub cold after extraction; add bridging prose if the structure feels gappy. The Groups and Profiles hubs are good shape references.

## Cross-link verification pass

When pages move, links to them from other files break. After each move, `grep -rn '<old-path>' docs/docs/` and for each match:

- Fix it now if it is inside the feature being migrated
- Record it in the `cross_links_to_update` section of the redirects-pending file if it is elsewhere

## Tutorial extraction is its own mini-migration

If a feature's guide moves to Academy, treat it as a self-contained subtask. See [tutorial-extraction](tutorial-extraction.md).

## Pre-PR user-perspective walk-through

Already part of [Step 9](../02-workflow/step-9-pre-pr-audit.md) for section-wide migrations. Spin up the dev server and click through every new page in the order a real user would encounter them. Look for:

- Orphan paragraphs (content that lost its context when extracted)
- Broken sidebar order
- Missing breadcrumbs
- Hub pages that read like stubs

This is a separate pass from the fact-check audit — it's a usability pass.

## TodoWrite per page

With 10+ pages being created, edited, or moved, a per-page todo prevents losing track. Each todo: "Extract `<X>` spoke from `<hub>.mdx` → `docs/<feature>/<x>.mdx` + verify build."

## Stop at build verification gates

Get feature N building cleanly before starting feature N+1. Compounding failures are harder to debug.

## Record cross-section work

Do not do work for another section here. Record it in Notion instead:

- Content that needs writing in another section: add a row to the [Docs content queue](https://app.notion.com/p/8e29c383844142919545717d2b89e5d9) with Topic set to Cross-section, filled in as [How to fill in a row in the Docs content queue](https://app.notion.com/p/3f4228b83025819d93a1deb4177e7f0c) describes.
- A structural gap, a decision you are deferring, or a cleanup task (redirects, legacy files, placeholder URLs): add it to the [Docs Revamp — Open Questions + Recommendations](https://app.notion.com/p/de5228b830258390891c0149aea768fe) page.

## One PR by default here too

"One feature at a time" above describes the **order you build things in**, not the number of pull requests. Convert one feature, check that it renders, then start the next — all on one branch, and propose one pull request for the section, per [Step 1](../02-workflow/step-1-preflight.md). If the user would rather have one per feature, follow that.

## Working against a shared branch

If the section migration is part of a longer programme that merges into a shared branch rather than the default branch, take the base branch from the user and branch from it, so each piece picks up the ones before it. Ask if you are unsure which base applies.

## Redirects are still pending across the docs

The redirect files accumulated in `docs/redirects-pending/` have not been applied yet — `@docusaurus/plugin-client-redirects` is not installed. Keep adding files there ([Step 7](../02-workflow/step-7-redirects.md)); installing the plugin and aggregating them is a separate job, not part of any migration.

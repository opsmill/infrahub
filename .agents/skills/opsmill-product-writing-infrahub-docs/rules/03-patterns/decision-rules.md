# Decision rules — which pattern fits

Pick a pattern by matching the source content shape to the table below.

> **Pattern decides where files go; [overview-page-content](overview-page-content.md) decides what the introducing page contains.** Whichever pattern you choose, the page a reader lands on first — hub, merged page, or new feature page — follows that content model. Read it alongside the pattern.

## Pattern selection

| Condition | Pattern |
|---|---|
| Single concept + one workflow, under ~300 lines | **Single-page merge** — one `docs/docs/<feature>/overview.mdx` |
| Multiple distinct tasks (3+ separable workflows) | **Hub + spokes** — short hub explaining the concept; one spoke page per task (Groups precedent) |
| The content is genuinely tutorial-shaped | **Tutorial extraction** — it moves to `academy/tutorials/<slug>.mdx`, keeping its title; the concept content stays as the feature page |
| Mix of tutorial + recipes | **Split** — tutorial portion → Academy; recipe portion → feature page (Groups precedent) |
| Multiple files sharing a name root + related procedural scope | **Likely single-page merge** even if file count > 2 — they're describing one feature |
| One page presenting N alternative ways to do the same job, whose purpose is helping the reader choose | **[Comparison page](comparison-page.md)** — 3–4 named categories, top summary, identical beats per option (create-objects precedent) |

**Default:** single-page merge unless the feature genuinely warrants more complexity.

## Content edit decisions during migration

| Issue type | Action |
|---|---|
| Clear factual error | Fix in this PR |
| Structural gap (missing prereqs, troubleshooting) | Flag to user; ask whether to fix or defer to post-launch |
| Stylistic improvement | Flag to user; default is defer |
| Outdated example | Flag to user; ask |
| Stale terminology or voice problems on pages you are not otherwise changing | Defer |

## Out of scope

- Editing pages in other sections. Record what needs doing there and leave them alone.
- Rewriting the voice of pages you are not otherwise changing.

Moving a whole sub-category to a different place in the sidebar **is** in scope when the agreed structure says so — the pages inside it move without being rewritten.

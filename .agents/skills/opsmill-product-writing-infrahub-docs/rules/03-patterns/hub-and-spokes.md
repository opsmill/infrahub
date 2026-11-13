# Hub + spokes

Used when a feature has 3+ separable workflows.

This file covers the file structure and the sidebar wiring. For what belongs on a hub versus a
spoke — and how much "why" each one carries — read
[hub-and-spoke-scope](hub-and-spoke-scope.md).

**Precedent:** Groups, Profiles.

## File structure

- **Hub** at `docs/docs/<feature>/overview.mdx` — concept content only. Every hub in the docs uses `overview.mdx`; `index.mdx` is not the convention here.
- **Spokes** at `docs/docs/<feature>/<task>.mdx` — one per task. Each spoke should have a brief "Next" or "Related" section at the bottom pointing to adjacent spokes.
- **Optional concept spoke** at `docs/docs/<feature>/<concept>.mdx` for substantial deep-dive content (e.g. priority and inheritance) when it's a frequently-referenced topic and would otherwise bloat the hub.
- **Optional Academy tutorial** at `docs/docs/academy/tutorials/<feature>.mdx`

## Hubs end with a catalog of their child pages

Every hub closes with an `## In this section` block listing its child pages in sidebar order, each with a short line saying what the reader gets there. Copy this format exactly — em dash as the separator, no full stop. `ipam/overview.mdx` and `schema/overview.mdx` are the working examples:

```mdx
## In this section

- [Create objects](https://docs.infrahub.app/objects/create-objects) — Compare every way to create an object, and see one created four ways
- [Metadata & lineage](https://docs.infrahub.app/objects/metadata) — Trace where each attribute value came from
```

**Why hubs are catalogs and not concept pages alone.** In the sidebar, clicking the arrow beside a category expands its child pages, while clicking the category name opens the hub. A reader who only ever clicks the arrow never sees the hub. Two approaches were considered. One was to make the category name jump straight to the first child page, which is what Kubernetes, Stripe, and GitHub do, and which removes the problem completely. The other was to keep the hub and make it worth arriving at. We chose the second: the hub is a scannable summary of what is underneath, so a reader who lands on it gets the map of the section, and a reader who skipped past it lost nothing the sidebar had not already shown them.

The sidebar is not a substitute for the catalog. Readers reach hubs from search results and from links on other pages, often part way down, where the sidebar may not be in view. A hub whose body contains no links to its own child pages leaves those readers with nowhere to go.

This is settled; apply it as written on each migration.

Use one catalog, at the bottom, in the format above. It is the page's only list of its children.

A "Learn by doing" body link to an Academy tutorial is also fine — the tutorial lives in a different sidebar section.

## Hub content: follow the overview page content model

A hub is the page a reader lands on to find out what the feature is for and how to approach it. What it must contain — the capability lead, the situation that makes the feature relevant, the concepts needed to decide, the paths with enough description to choose between them, and where to go next — is specified once in [overview-page-content](overview-page-content.md). Read it before drafting a hub.

Mechanics — request flows, "how it works" step lists — come *after* that framing, not instead of it.

**Failure mode caught there:** an overview that ships accurate but mechanics-first — deep on the internal flow, but never saying what the feature is for, and offering no comparison to the alternatives. Accurate, yet it doesn't help the reader decide.

## Critical: hub categories must have a clickable link

In `sidebars.ts`, every category that becomes a hub must include:

```ts
link: { type: 'doc', id: '<feature>/overview' }
```

Without this, the category caret expands but the label itself is dead — clicking "Profiles" or "Branches" does nothing. The Groups, Profiles, and Branches categories all have this; it's a recurring bug to forget. Verify after writing the sidebar entry.

## Hub-after-extraction review

When a hub loses its H3 content to spokes, verify the hub still reads as a coherent concept page on its own — not a stub. Re-read the hub cold after extraction; add bridging prose if the structure feels gappy. The Groups and Profiles hubs are good shape references.

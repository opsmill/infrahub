# Tutorial extraction

Used when the legacy guide is genuinely tutorial-shaped — a coherent end-to-end scenario rather than a recipe.

## Apply the scenario-shape test first

Before extracting, run the [tutorial scenario-shape test](../01-principles/tutorial-shape-test.md). If the guide is feature-oriented (sequence numbers stuck on existing content) rather than scenario-oriented (a real learning arc), **drop the tutorial** from this PR and log a follow-up for a scenario rewrite.

## Extraction steps

- Move guide to `docs/docs/academy/tutorials/<slug>.mdx`
- Preserve original title (e.g. "How to organize objects with groups" stays the same)
- Reframe as tutorial: add "By the end of this tutorial you will…" preamble; "What you learned" closer
- Topic page may need light edits if it referenced the old guide

## Tutorial opener convention

An Academy tutorial states its framing and its outcomes once. Saying them twice — a "This tutorial
walks you through…" intro *and* a "By the end of this tutorial you will:" list naming the same
outcomes — makes the reader read the same information in two forms before the work starts.

What the opener needs to establish is what the reader will have built by the end, in enough detail
that they can tell whether it is the tutorial they wanted: "By the end of this tutorial you will have
built, deployed, and validated …". See `academy/tutorials/groups.mdx` and
`academy/tutorials/build-a-check.mdx` for the precedent.

## Treat tutorial extraction as its own mini-migration

If a feature's guide moves to Academy, treat it as a self-contained subtask with its own checklist:

- Source location → destination
- Title change
- Placement decision (which Tutorials sub-category)
- Cross-link from the source feature page back to the tutorial

Keep it as its own step, separate from the hub-conversion work for the same feature.

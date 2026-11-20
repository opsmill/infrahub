# Step 2.5 — Spec review against skill rules ★ (when a recommendations doc exists)

When the user provides a Notion recommendations doc (typical for section-wide migrations), the doc replaces Steps 2 and 3 as the planning artifact. But the doc may have gaps — review it critically against the skill's decision rules before implementing.

## Cross-check against the navigation map

For Infrahub main repo work, before running the checklist below, **cross-check the recommendations doc against [docs-navigation-map](../04-infrahub/docs-navigation-map.md).** Specifically:

- Is the content placed in the right top-level section per the map's "Goes here / Does NOT go here" guidance?
- If the content spans multiple sections (e.g. a primitive that's operationally relevant), did the doc pick the right canonical section per the "When content could fit in multiple sections" rules?
- If the content involves a satellite repo (Sync, SDK, Ansible, Nornir, infrahubctl, MCP), did the doc pick the right canonical repo and call out the cross-repo PR split?
- Did the doc pick the right Diátaxis quadrant placement (concept → hub, how-to → spoke, tutorial → Academy, reference → Reference section)?

Mis-placements are common and worth surfacing early; they're harder to fix after drafting.

## The checklist

Read the doc end-to-end. Then run this checklist against the proposed structure:

- **A concept page and a how-to describing the same single feature, treated as separate moves.** That is a **single-page-merge candidate** per the [decision rules](../03-patterns/decision-rules.md) — merge them rather than carrying the split forward.
- **Shared name roots that suggest merging.** If multiple files share a name root (e.g. `branch-synchronization` + `selective-branch-sync`) AND describe related procedural work, they're merge candidates. Treat them as one feature unless there's a specific reason to keep them separate.
- **Hub categories without a clickable link.** Every category that becomes a hub in `sidebars.ts` must have `link: { type: 'doc', id: '<feature>/overview' }`. Without that, the category caret expands but the label is dead. Confirm the doc specifies an explicit hub for each new category.
- **Tutorial-shaped guides not being extracted.** Run the [tutorial-shape check](../01-principles/tutorial-shape-test.md) (Step 1/2/3 headings, single running example, narrative arc) on every guide in the spec. If a guide is tutorial-shaped but the doc says "keep here," ask whether to extract or reframe.
- **Missing common spokes.** When converting a feature to hub+spokes, common operations (`create`, `update`, `delete`, `query`, etc.) typically each get a spoke. If the doc lists 3 spokes but obvious operations are missing, flag it.
- **Broken cross-link patterns.** When a feature moves into a sub-section (e.g. Git Integration nesting under Branches & Change Control), pages from that sub-section reference each other via paths that may need updating.

## Per the meta-rule

Every finding gets presented to the user with rationale, not silently applied. See [gate-discipline.md](../01-principles/gate-discipline.md). The user updates the doc, then you implement against the updated spec.

★ **Gate**: present spec-review findings. User decides which to add to the spec, which to leave as-is. Once decisions land, the user (or you, on their behalf) updates the recommendations doc to reflect the final spec. Then proceed to Step 4.

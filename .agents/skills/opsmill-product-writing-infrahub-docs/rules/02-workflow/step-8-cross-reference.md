# Step 8 — Cross-reference scan

Find every page that references the legacy paths and decide what to do with each.

> **Other repos:** substitute the resolved docs root from [Step 0.5](step-0.5-detect-repo.md) wherever `docs/docs/` appears.

## The scan

- Run `grep -rln '<feature-slug>' docs/docs/` to find inbound references to the legacy paths.
- For each, identify whether the page actually mentions / depends on the migrated feature (vs a path coincidence).

## Handling each match

- **Pages in other sections that should reference this feature in CONTENT (not sidebar):** add a row to the [Docs content queue](https://app.notion.com/p/8e29c383844142919545717d2b89e5d9) in Notion with Topic set to Cross-section, filled in as [How to fill in a row in the Docs content queue](https://app.notion.com/p/3f4228b83025819d93a1deb4177e7f0c) describes. **Do NOT modify those other-section pages in this PR** — out of scope.
- **Pages in other sections that have stale Markdown links to legacy paths** (will resolve via redirect at runtime but should be updated to new paths at cleanup): add an entry to the redirects-pending file's `cross_links_to_update` section with `file`, `line`, `current` link target, and `should_be` link target. This gives the cleanup PR a complete inventory.
- **Internal cross-links within the feature itself** (e.g. spokes referencing each other, hub referencing spokes) that are now stale: **fix them in this PR.**

## Why the split

Cross-section content edits are out of scope for individual feature-migration PRs — they belong in a coordinated cleanup pass. But within-feature stale links break the feature's own pages, so they must be fixed in the migration PR or the new structure ships broken.

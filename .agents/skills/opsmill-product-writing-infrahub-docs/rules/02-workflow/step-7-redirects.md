# Step 7 — Add redirects-pending file

> **Other repos:** This is an Infrahub-main convention. If the repo resolved in [Step 0.5](step-0.5-detect-repo.md) has no redirects mechanism, skip this step entirely and note in the PR description ("Redirects: none — this repo doesn't have a redirects mechanism. Manual updates to inbound links may be needed."). If the repo has a different redirects mechanism (`_redirects` file, MkDocs plugin, etc.), adapt the schema to match.

## Why this exists

When pages move, record the URL changes in a YAML file under `docs/redirects-pending/`. Each file has three sections: the redirects themselves (old URL → new), the new pages introduced, and links in other files that still point at the old paths. The redirect plugin is not installed yet, so these files accumulate until someone applies them in one pass. See `docs/redirects-pending/README.md` for the schema.

## Create the file

Create `docs/redirects-pending/<feature-or-section-slug>.yml`:

```yaml
---
feature: <Feature Name or Section Name>
pr: TBD
description: |
  Brief explanation of what changed and why these redirects exist.

# Legacy URLs that will redirect to new locations
redirects:
  - from: /docs/<old-path>
    to: /docs/<new-path>

# Net-new pages introduced by this migration (canonical URLs for cross-reference)
new_pages:
  - path: /docs/<feature>/
    title: <Feature> (hub)
  - path: /docs/<feature>/<task>
    title: <Task title>

# Internal cross-link references in OTHER files that point at legacy paths
# (will resolve via redirect at runtime but should be updated to new paths at cleanup)
cross_links_to_update:
  - file: docs/docs/<other-section>/some-page.mdx
    line: 42
    current: ../<old-path>
    should_be: ../<feature>/
```

## Common patterns for the `redirects` section

- **Hub + spokes** — every old URL redirects to the new hub:
  - `/docs/<old-path>` → `/docs/<feature>/`
- **Single-page merge** — the old URLs redirect to the merged page:
  - `/docs/<old-path>` → `/docs/<feature>/`
- **Tutorial extraction** — the old URL redirects to the feature page. The tutorial's URL is new, so it needs no redirect.

## Update the index

Update `docs/redirects-pending/README.md` "Files in this folder" table to add the new entry.

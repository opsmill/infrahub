# Redirects pending

Each migration drops a YAML file in this folder recording the URL changes the migration introduces. At the end of Phase 2 (when the docs revamp is ready to ship to production), all files here are aggregated — `redirects` sections compile into a single `redirects:` array in `docs/docusaurus.config.ts` via `@docusaurus/plugin-client-redirects`; `cross_links_to_update` sections become the cleanup checklist for fixing stale internal links across other docs.

This folder exists so we don't need to maintain a single growing redirects configuration across feature PRs — each PR lands its own self-contained file, and the cleanup PR at the end consolidates them.

## File format

One YAML file per feature or section, named `<feature-or-section-slug>.yml`. Three sections, all optional but typically all populated:

```yaml
---
feature: <Feature Name or Section Name>
pr: <PR-number-or-URL>
description: |
  Brief explanation of what changed and why these redirects exist.

# Legacy URLs that will redirect to new locations
redirects:
  - from: /docs/<old-path>
    to: /docs/<new-path>
  - from: /docs/<another-old-path>
    to: /docs/<another-new-path>

# Net-new pages introduced by this migration (canonical URLs for cross-reference)
new_pages:
  - path: /docs/<feature>/
    title: <Feature> (hub)
  - path: /docs/<feature>/<task>
    title: <Task title>

# Internal cross-link references in OTHER files that point at legacy paths
# (will resolve via redirect at runtime but should be updated to new paths at cleanup)
cross_links_to_update:
  - file: docs/docs/topics/some-other-page.mdx
    line: 42
    current: ../topics/<slug>
    should_be: ../<feature>/
```

### Fields

- **feature** — display name of the feature or section being migrated
- **pr** — PR number or URL that introduced this redirect file (fill in once the PR is open)
- **description** — short prose explaining what changed
- **redirects** — list of `{from, to}` URL pairs. These get installed as runtime redirects via `@docusaurus/plugin-client-redirects` at end-of-Phase-2.
- **new_pages** — list of `{path, title}` for pages that didn't exist before this migration. Useful for: future migrations that want to cross-link to these pages; cleanup PR knowing what's new vs. moved; team understanding of what the migration produced.
- **cross_links_to_update** — list of `{file, line, current, should_be}` for stale Markdown links in OTHER files that point at the legacy paths. These will resolve via the runtime redirects, but should be rewritten to the new paths at cleanup time so the source content is clean. Track them here so the cleanup PR has a complete inventory.

### Why we track all three

- **`redirects`** is the runtime concern (URL still works after structure change).
- **`new_pages`** is the discoverability concern (anyone writing future content needs to know where to link).
- **`cross_links_to_update`** is the source-cleanliness concern (post-cleanup, source files shouldn't reference paths that no longer exist).

Only `redirects` is consumed by the redirect plugin. The other two sections are metadata for humans and the cleanup PR.

## End-of-phase-2 aggregation steps

When ready to ship to production:

1. Aggregate all `*.yml` files' `redirects` sections into a single redirects array.
2. Install the plugin: `npm install --save-dev @docusaurus/plugin-client-redirects` (matching version of other `@docusaurus/*` packages).
3. Add the plugin to `docs/docusaurus.config.ts` plugins array with the aggregated redirects.
4. Verify each old URL redirects correctly (`npm run build && npm run serve`).
5. Walk through each YAML file's `cross_links_to_update` section. For each entry, edit the source file to use the `should_be` link target instead of `current`.
6. Delete the legacy `topics/<slug>.mdx` and `guides/<slug>.mdx` files for each migrated feature.
7. Delete this folder once the redirects are live in `docusaurus.config.ts` and all cross-links are updated.

See [Docs Revamp — URL Migration & Redirects](https://opsmill.atlassian.net/wiki/spaces/Product/pages/550928392/Docs+Revamp+URL+Migration+Redirects) for the full implementation guide.

## Files in this folder

| File | Feature / Section | PR |
|---|---|---|
| `profiles.yml` | Profiles | https://github.com/opsmill/infrahub/pull/9114 |
| `computed-attributes.yml` | Computed Attributes | https://github.com/opsmill/infrahub/pull/9120 |
| `branches-and-change-control.yml` | Branches & Change Control | TBD |
| `menu.yml` | Menu Customization | TBD |
| `schema.yml` | Schema & Data | TBD |
| `deploy-manage-hardware-requirements.yml` | D&M — Hardware Requirements (sidebar scaffold) | TBD |
| `deploy-manage-installation.yml` | D&M — Installation (hub + Community + Enterprise spokes) | TBD |
| `deploy-manage-production-deployment.yml` | D&M — Production Deployment (hub + HA spoke) | TBD |
| `deploy-manage-configure-infrahub.yml` | D&M — Configure Infrahub | TBD |
| `deploy-manage-run-observe.yml` | D&M — Run & observe (Tasks, Telemetry, Activity Log) | TBD |
| `deploy-manage-log-forwarding.yml` | D&M — Log Forwarding (hub + Configure spoke) | TBD |
| `deploy-manage-database-backup.yml` | D&M — Database Backup (hub + 2 spokes) | TBD |
| `deploy-manage-upgrade.yml` | D&M — Upgrade (hub + 3 spokes) | TBD |
| `deploy-manage-authentication.yml` | D&M — Authentication (move) | TBD |
| `deploy-manage-sso.yml` | D&M — SSO (hub + 2 spokes) | TBD |
| `deploy-manage-permissions-roles.yml` | D&M — Permissions & Roles (hub + 1 spoke) | TBD |
| `deploy-manage-api-tokens.yml` | D&M — Managing API Tokens (page move) | TBD |
| `development-resources.yml` | Development Resources (page moves + APIs & interfaces flat structure) | TBD |

# Redirects pending

Each feature-page migration drops a YAML file in this folder describing the URL redirects that the migration introduces. At the end of Phase 2 (when the docs revamp is ready to ship to production), all files here are aggregated into a single `redirects:` array in `docs/docusaurus.config.ts` via `@docusaurus/plugin-client-redirects`.

This folder exists so we don't need to maintain a single growing redirects configuration across feature PRs — each PR lands its own self-contained file, and the cleanup PR at the end consolidates them.

## File format

One YAML file per feature, named `<feature-slug>.yml`:

```yaml
feature: <Feature Name>
pr: <PR-number>
description: |
  Brief explanation of what changed and why this redirect is needed.
redirects:
  - from: /docs/<old-path>
    to: /docs/<new-path>
  - from: /docs/<another-old-path>
    to: /docs/<another-new-path>
```

Fields:

- **feature** — display name of the feature being migrated
- **pr** — PR number that introduced this redirect file (fill in once the PR is open)
- **description** — short prose explaining what changed
- **redirects** — list of `{from, to}` URL pairs

## End-of-phase-2 aggregation steps

When ready to ship to production:

1. Run an aggregation script (or manually compile) all `*.yml` files in this folder into a single redirects array.
2. Install the plugin: `npm install --save-dev @docusaurus/plugin-client-redirects` (matching version of other `@docusaurus/*` packages).
3. Add the plugin to `docs/docusaurus.config.ts` plugins array with the aggregated redirects.
4. Verify each old URL redirects correctly (`npm run build && npm run serve`).
5. Delete the legacy `topics/<slug>.mdx` and `guides/<slug>.mdx` files for each migrated feature.
6. Update inbound cross-links in other docs to point at new paths.
7. Delete this folder once the redirects are live in `docusaurus.config.ts`.

See [Docs Revamp — URL Migration & Redirects](https://opsmill.atlassian.net/wiki/spaces/Product/pages/550928392/Docs+Revamp+URL+Migration+Redirects) for the full implementation guide.

## Files in this folder

| File | Feature | PR |
|---|---|---|
| `profiles.yml` | Profiles | TBD |

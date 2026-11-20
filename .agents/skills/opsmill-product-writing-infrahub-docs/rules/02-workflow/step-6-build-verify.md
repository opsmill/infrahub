# Step 6 — Build + verify

Build the docs and fix anything broken before continuing.

## Infrahub main

```bash
cd docs && npm run build
```

Fix any broken doc IDs or links. The build is the broken-link check — `docusaurus.config.ts` sets `onBrokenLinks: "throw"`, so a passing build means every internal link resolves. Run `npm run serve` to visually check.

### Two dev-server gotchas (both cost real review time)

- **`npm run build` kills a running dev server** on the same port. If the user is reviewing on a live preview, don't run the build mid-review — you'll hand them a dead link. Run the build before starting the preview or after the review round, and restart the server (and say so) if you had to build.
- **Preview URLs have no `/docs/` prefix.** Infrahub main serves docs at the site root (`baseUrl: "/"`, `routeBasePath: "/"`): the page is `http://localhost:3000/objects/create-objects`, not `/docs/objects/create-objects`. The wrong URL still returns HTTP 200 (single-page app) and renders the 404 page — so check content, not status codes, when verifying, and give the user root-relative links.

## Other repos

Use the repo's own build tooling (e.g. `mkdocs build`, `pnpm docs:build`, repo Makefile target). If there is no docs build, skip — but flag in the PR description that no automated render check was possible.

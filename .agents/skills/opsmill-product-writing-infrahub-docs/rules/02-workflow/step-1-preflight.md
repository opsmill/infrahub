# Step 1 — Pre-flight

Get the working tree clean and the branch right before touching files.

## How many pull requests

**Propose one pull request covering the whole scope of the work**, whatever its size, and confirm that with the user before creating any branches. Something like: "I'll put all six pages in one pull request — tell me if you'd rather split it."

They may want it differently, and that is their call. Ask once, at the [Step 3](step-3-outline.md) outline gate when the scope is clear, and follow whatever they say.

Propose more than one only when there is a technical reason, such as changes in different repositories, which always need separate pull requests because each repository runs its own CI ([Step 0.5](step-0.5-detect-repo.md)). If you propose a split, say why in one sentence and let the user decide.

If something is deliberately left for a later pull request, say so in the description of the current one so that it does not look like an oversight, and remind the user once the first one is merged.

## Steps

- Verify you are on the base branch — the repository's default branch unless the user names another one. [Step 0.5](step-0.5-detect-repo.md) resolves it.
- Run `git status -s`. Any uncommitted changes? Stop and ask user how to handle them before creating a new branch.
- Create one branch for the agreed scope, named for the work rather than for one of its parts: `docs/<slug>` (e.g. `docs/objects-create-rework`, `docs/migrate-profiles`, `docs/migrate-branches-and-change-control`).
- Confirm the local serve and build work as a baseline (Infrahub main: `cd docs && npm run build`).

> **Other repos:** use the branch naming convention resolved in Step 0.5. Verify the local build works with the repo's own build tooling.

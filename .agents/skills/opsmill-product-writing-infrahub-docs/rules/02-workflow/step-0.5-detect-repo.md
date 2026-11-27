# Step 0.5 — Work out where things are in this repository

Most of the time this skill runs against the **Infrahub main repo**, where the paths below apply as written. In any other repository the paths differ, so work out the equivalents by reading the repository. Do not ask the user questions you can answer yourself — most docs repositories are laid out the same way, and the few facts this step needs are all discoverable.

## A different repository changes paths, not the workflow

The problem observed in other repositories is not incorrect paths. It is **skipped steps**: whole steps left out, gates never presented to the user, and principle files never applied, because the workflow appeared to be specific to Infrahub. It is not. In another repository:

- **Every numbered step still runs, in order.** If a step needs something this repository does not have — no sidebar file, no redirects, no docs build — say which step you are skipping and why, both at the time and in the pull request description. For example: "Step 7 skipped: this repository has no redirects mechanism." Skipping a step without saying so is the problem this rule addresses.
- **Every ★ gate still gates.** Triage, audit, spec review, content audit, outline, pre-PR audit, PR description — none of these are Infrahub-main features. They are the workflow.
- **Every file in `rules/01-principles/` still applies** — not only voice and jargon: gate-discipline, audit-rigor, spec-drift, corrections-ledger, tutorial-shape, steps-vs-sections. The Step 2.7 benchmark and its accuracy guardrail apply everywhere too.
- The Infrahub-only pieces are exactly two: the `rules/04-infrahub/` navigation map, and the Infrahub-main defaults table below. Everything else is repo-agnostic with a substituted mechanism.

If you are unsure whether a step applies, assume it does, using this repository's equivalent tooling. If there is no equivalent, say which step you are skipping and why.

## The check

Run `git remote get-url origin` at the start of every session, after Step 0. If it is Infrahub main (`opsmill/infrahub`), use the defaults below as written and continue to Step 1. Otherwise, detect the equivalents as described further down.

## Infrahub main defaults

These are baked into the workflow steps. If the repo matches Infrahub main, the steps work as written.

| Item | Infrahub main default |
|---|---|
| Docs root | `docs/docs/` |
| Sidebar file | `docs/sidebars.ts` (Docusaurus) |
| Redirects mechanism | `docs/redirects-pending/` YAML files |
| Default base branch | `stable` |
| Branch naming | `docs/<feature-slug>` |
| Build command | `cd docs && npm run build` |
| Lint command | `uv run invoke docs.lint` |

## Detecting the equivalents in another repository

Read the repository rather than asking. Each of these takes one command:

| What you need | How to find it |
|---|---|
| Docs root | Look for `docs/`, `documentation/`, or a site config — `docusaurus.config.*`, `mkdocs.yml`, `mint.json`. If there is none, the repository is README-only. |
| Sidebar mechanism | Docusaurus keeps it in `sidebars.*`; MkDocs uses the `nav:` block in `mkdocs.yml`; some sites generate it from the directory tree, in which case there is nothing to edit. |
| Redirects | Check for `redirects-pending/`, a `_redirects` file, `netlify.toml`, or `@docusaurus/plugin-client-redirects` in `package.json`. If none exist, Step 7 does not apply here. |
| Default branch | `git symbolic-ref refs/remotes/origin/HEAD`, or `gh repo view --json defaultBranchRef`. |
| Branch naming | `git branch -r --sort=-committerdate \| head -20` shows the convention in use. `CONTRIBUTING.md` or `AGENTS.md` may state it. |
| Build and lint commands | The scripts in `package.json`, or the tasks in `Makefile`, `noxfile.py`, or `tasks/`. |

State what you found in one short line — "docs in `docs/`, MkDocs nav, no redirects mechanism, default branch `main`" — so the user can correct anything wrong. **Only ask when detection is genuinely ambiguous**, such as two docs directories with no obvious primary, and ask about that one thing rather than running through a list.

## Skip-and-flag for missing layers

If a layer doesn't exist in the resolved repo, **skip the corresponding workflow step** and mention it in the PR description.

Most common case: **no redirects mechanism**. Skip Step 7 entirely. Note in PR: "Redirects: none — this repo doesn't have a redirects mechanism. Manual updates to inbound links may be needed."

## Voice and tone are repo-agnostic

Even when working in another repo, the voice rules ([voice-and-tone.md](../01-principles/voice-and-tone.md), [audit-rigor.md](../01-principles/audit-rigor.md)) **still apply**. Match the voice of the well-regarded OSS docs the skill targets — same standard everywhere. The repo's local lint config may or may not enforce this; the skill enforces it regardless.

## Cross-repo content overlap

When working in a satellite repo (Sync, SDK, Ansible, Nornir, infrahubctl, MCP), the work sometimes touches main Infrahub too. Before committing in this repo, ask: **does any of this content also need to land in main Infrahub?** See the "Cross-repo placement" section of [docs-navigation-map](../04-infrahub/docs-navigation-map.md) for the rules.

If yes, the satellite PR ships first or in parallel; main Infrahub gets its own branch and PR for the linked content. Don't bundle changes across repos into one PR — they live in separate repos and each repo's CI runs separately.

# Step 11 — Lint, commit, push, open PR

## Always lint before committing

Required by `docs/AGENTS.md`:

```bash
uv run invoke docs.lint
```

This runs both markdownlint and Vale. **Both must pass** — Vale (documentation style) failures block CI in the `validate-documentation-style` check. Fix every error reported before committing. Warnings are not blocking but should be triaged: if a warning is in NEW content, fix it; if it's in pre-existing content unrelated to this PR, leave it.

> **Verify each lint tool actually ran** — don't infer from a clean wrapper exit. Some tools silently skip if not installed — `uv run invoke docs.lint` exits 0 even when Vale didn't run because the binary is missing. Run `which vale` first, or look for Vale's per-file output. Markdownlint passing ≠ Vale ran.

If Vale isn't installed locally, install it first — `brew install vale` on macOS, or download from <https://github.com/errata-ai/vale/releases>. Don't skip Vale checks; CI will catch what you missed and you'll have to push fix-up commits.

### When the tooling itself is missing (sandboxed/web environments)

Some environments have no `uv` and no `vale`, and installing them isn't possible. Run what exists and account for the rest — never report "lint passed" when a tool never ran:

- **markdownlint without uv:** the binary ships with the docs dependencies. From the repo root (so the repo's `.markdownlint-cli2.yaml` config applies — running from `docs/` picks up different globs):

  ```bash
  ./docs/node_modules/.bin/markdownlint-cli2 'docs/docs/<changed-files>.mdx'
  ```

- **Vale unavailable:** run the manual word check below plus the voice failure-mode pass from [Step 9](step-9-pre-pr-audit.md), and state in the PR description which checks will run only in CI (`validate-documentation-style`) — so a CI failure there is expected-and-owned, not a surprise.

> **Other repos:** Use the repo's own docs lint command, or skip if there is none. The voice rules still apply when Vale is unavailable — run the manual word check below.

## Common Vale rules to watch for

- **`Infrahub.spelling`** — flags non-dictionary words. Either rephrase, or if it's a real word that should be in the vocabulary, add it to `.vale/styles/spelling-exceptions.txt`.
- **`Infrahub.swap`** — substitutes specific terms (e.g. "repo" → "repository"). Use the preferred term.
- **`Infrahub.branded-terms-case-swap`** — Infrahub product names should be capitalized (Transformations, Generators, Profiles, etc.) when used as branded references.
- **`Infrahub.eg-ie`** (warning) — replace `e.g.` and `i.e.` with `for example,` or `that is,`.
- **`Infrahub.sentence-case`** (warning) — headings should use sentence case, not title case.
- **`Infrahub.simple-easy`** (warning) — flags `easy`, `simple` and `simply`
  (`.vale/styles/Infrahub/simple-easy.yml`). It does **not** cover `easily` or `just`, which is why the manual
  check below still exists.

For dev-internal docs that shouldn't be subject to Vale style rules (team workflow READMEs, planning artifacts), add a `BasedOnStyles =` exclusion in `.vale.ini` rather than fighting individual rules. Examples already excluded: `docs/docs/reference/**`, `docs/redirects-pending/**`, `**/AGENTS.md`.

## Manual word check

`Infrahub.simple-easy` covers `easy`, `simple` and `simply`; `easily` and `just` are not in that rule, so
check them here. Run this against **every file changed in the PR** — not just the docs pages, but also any skill, agent guide, or dev doc you touched. The forbidden-words rule is global; in-house dev docs aren't exempt.

```bash
git diff --name-only origin/<base-branch>...HEAD \
  | xargs grep -niE '\bsimple\b|\bsimply\b|\beasy\b|\beasily\b|\bjust\b' 2>/dev/null
```

If any matches are in NEW content (whether docs or skill/dev files), fix in place. If matches are in PRESERVED content, propose fixing as part of the migration since the file is shipping under the new structure (the Profiles migration set this precedent).

## Changelog — not for documentation-only changes

Documentation-only changes do **not** get a changelog fragment. Infrahub's `changelog/` fragments track user-facing product changes — features, fixes, security, housekeeping — for release notes, not edits to the docs site. Adding one to a docs PR is noise a reviewer will ask you to remove.

- A PR that only touches `docs/` needs no `changelog/+<slug>.<type>.md` fragment.
- If the `commit` skill offers to add one, decline. If a fragment was already added, delete it before opening the PR.
- The exception is a change that also alters product behavior or a user-facing string. There the fragment covers the code change, not the docs.

> **Other repos:** follow the target repo's convention. Where it is unclear, docs-only changes still default to no fragment.

## Commit, push, and open the PR — delegate to the `commit` and `pr` skills

Do **not** hand-roll `git add` / `git commit` / `git push` / `gh pr create` here. Branch discipline, commit hygiene, the ship gate, and CI monitoring are owned by the **opsmill-product** plugin — reuse them so the rules live in one place and this skill inherits the gate for free. This is a hard dependency (see the plugin's `AGENTS.md`); only fall through to raw git if opsmill-product is genuinely unavailable.

Hand off only **after** docs lint and the word check above pass — that is this skill's contribution to the gate.

A passing lint is not the review. Before handing off, confirm four things, whatever the use case ([what the smaller-update shortcut covers](../../SKILL.md#what-the-smaller-update-shortcut-covers)):

- The [Step 9](step-9-pre-pr-audit.md) gate was presented and confirmed.
- The checks file (`dev/specs/docs/<slug>.checks.md` in Infrahub main) exists and holds both walks from [checking-prose](../01-principles/checking-prose.md), with their counts.
- The [Step 10](step-10-pr-description.md) body was approved, and its verification part carries those counts and the rules-read list.
- The lint line in that body now holds the results from this step. The body was approved at Step 10 with the lint line marked as pending, so filling it in is the one edit allowed after approval. If a tool failed or did not run, show the user the updated line before handing off.

When the user asked to skip the gates ([skipping the process](../../SKILL.md#when-the-user-asks-you-to-skip-the-process-or-the-rules)), the Step 9 gate and the Step 10 approval are in the one message at the end that combines the skipped gates. Once the user approves that message, the first and third items are met. Do not ask for the skipped gates again.

If any of the four is missing, go back to that step. Do not report the page as verified on the strength of Vale, markdownlint and the build.

**REQUIRED SUB-SKILL — `commit`:** invoke `/commit push`. It refuses protected branches (`main`/`stable`/release), proposes a `docs/<slug>` feature-branch name for your approval, stages the doc files, drafts a conventional `docs:` commit message, runs pre-commit hooks (no `--no-verify`), and pushes upstream. Do not create the branch or commit yourself.

**REQUIRED SUB-SKILL — `pr`:** once the branch is pushed, hand off to `pr` to open the PR. Give it:

- the **base branch** resolved at [Step 0.5](step-0.5-detect-repo.md) (Infrahub-main: the docs-revamp base; other repos: their default);
- the **PR body approved at [Step 10](step-10-pr-description.md)** as the description. It is already built on the repository's PR template with the docs content placed under its headings, which is what `pr`'s own rule ("the repo template wins") asks for. Hand it over as it is; do **not** let `pr`'s generic body template replace it or add sections to it;
- the title from Step 10.

`pr` opens the PR after the user approves the description, then spawns `monitoring-pull-requests` in the background to watch CI. `writing-infrahub-docs` inherits both by delegating.

> **Optional independent verdict:** for an author≠judge check before the PR opens, run `/opsmill-product-judging-changes` with the approved recommendations doc / JPD card / messaging brief from [Step 0](step-0-triage.md) (or the user's stated goal) as the criteria source — never your own draft summary. Only repos that enforce ship-gate receipts (`.claude/quality-gates/enabled`) require it.

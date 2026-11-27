---
name: opsmill-dev-analyzing-dependency-bumps
description: >-
  Produces a breaking-change / deprecation / opportunity report for a dependency-bump PR,
  grounded in how this codebase actually uses each bumped package, not the changelog alone.
  TRIGGER when: the user gives a PR URL or number for a dependency version bump (Dependabot,
  Renovate, or hand-rolled) and asks what could break, what changed, or whether it is safe to
  merge (e.g. "scan this dependabot PR", "what breaks if we take this bump", "is <PR url> safe
  to merge"). DO NOT TRIGGER when: the PR is a feature or bugfix rather than a dependency version
  bump → a code-review or bug skill instead.
argument-hint: <PR url or number for a dependency bump>
compatibility: >-
  Requires GitHub access to fetch the PR (gh CLI authenticated, GitHub MCP server, or
  equivalent) and a checkout of the target repo to grep real usage. Read-only — never edits,
  merges, or comments unless explicitly asked.
metadata:
  version: 0.1.0
  author: OpsMill

user-invocable: true
---

# Analyze Dependency Bump

Given a dependency-upgrade PR, produce a breaking-change / deprecation / opportunity report **grounded in this repo's actual usage**. The governing principle:

> A changelog tells you what changed in the library. Only the codebase tells you whether it matters here.

Every claim in the report must trace to real usage in the repo — or to the verified *absence* of usage. A "safe to merge" backed only by the changelog is not allowed.

## Output contract

A **chat report** — do not write files or post PR comments unless the user explicitly asks. Lead with a one-line verdict, then one section per bumped package:

```text
Verdict: <safe to merge | needs code changes | review required>

## <package> <old> → <new>
- Classification: direct | transitive  (chain: pkg ← parent ← … ← root)
- Usage in repo: <file:line refs, or "none — no imports">
- Breaking changes: <each labeled impacts-us | not-used | role-mismatch>
- Deprecations: <each + whether the repo hits it>
- Security / bug fixes: <the relevant ones only>
- Opportunities: <new APIs/defaults worth adopting, with code refs>
- Recommendation: <concrete next step>
```

Hard rules for the report:

- Every **safe** claim is backed by either no-usage (with the grep that proves it) or a verified role mismatch. Never assert safety from the changelog alone.
- Every **impacts-us** claim cites `file:line` and names the required code change.
- Keep it dry and specific. No filler, no restating the PR body.

## Workflow

Detect the ecosystem from the manifest/lockfile the PR touches and use its lockfile, reverse-dep tool, and import idiom. When a repo mixes ecosystems, run the steps once per affected ecosystem.

### 1. Fetch the PR and extract every version bump

```bash
gh pr view <num> --repo <owner/repo> --json title,body,files,headRefName,baseRefName
gh pr diff <num> --repo <owner/repo>
```

Parse the **lockfile diff** (`uv.lock`, `poetry.lock`, `package-lock.json`, `pnpm-lock.yaml`, `Cargo.lock`, `go.sum`, etc.) for exact `old → new` versions — do not trust the title alone. A bot PR names one package in the title even when the lock pulls in several. Handle both single and grouped bumps. If only a number is given and the repo is ambiguous, infer from the cwd's `git remote` or ask.

### 2. Classify each bump: direct vs transitive

This decides everything downstream.

- **Direct** — listed in the manifest (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`), including dev/optional/group sections.
- **Transitive** — only in the lockfile, pulled in by another package.

For transitive packages, compute the reverse-dependency chain and report it (e.g. `certifi ← httpx ← pytest-httpx`, terminating in a dev-only test tool). Depth, and whether the chain terminates in a **runtime** vs **dev/test** dependency, is a primary impact signal. Use the ecosystem's reverse-dep tool (`npm ls <pkg>`, `cargo tree -i <pkg>`, `go mod why <pkg>`, …), or parse the lockfile's resolved graph directly (e.g. `uv.lock` TOML `[[package]]` → `dependencies` / `optional-dependencies` / `dev-dependencies`) to build a reverse map — the latter needs no synced environment.

### 3. Grep real usage in the repo

Grep the repo for the package's import idiom — first to find imports of the package, then to find the specific symbols the changelog flags:

```bash
# Python example — substitute the import pattern + --include glob per ecosystem
grep -rn "import <pkg>\|from <pkg>" --include="*.py" .
grep -rn "<ChangedSymbol>\|<deprecated_fn>" --include="*.py" .
```

Guard against **symbol collisions** — a name can belong to a different library (e.g. `request.url` on an `httpx` object is not `starlette`; a `parse()` could come from any of several deps). Confirm the import source before counting a match. **Zero direct imports is a strong, citable result**: most changelog entries then cannot apply — say so plainly.

### 4. Read the full changelog for every bump (deep by default)

For every bumped package, direct or transitive, read release notes spanning the **whole** `old → new` range — breaking changes hide in intermediate versions, not just the endpoints.

- The PR body usually embeds the bot's release-notes / changelog / commits sections. Read them.
- When truncated or missing, fetch upstream with `WebFetch` (`https://github.com/<owner>/<repo>/compare/<old>...<new>`, the `CHANGELOG`), or use the Context7 MCP for the library's migration docs.
- If the notes still can't be retrieved (private upstream, no published changelog, no network), **ask the user to paste the release notes or a link** rather than guessing. Never invent changelog content — say which versions you couldn't source and report only what the repo's usage lets you verify.

Categorize each notable change: **breaking**, **deprecation**, **security fix**, **bug fix**, **new capability**.

### 5. Cross every changelog item against actual usage

Label each notable change by its relevance *to this repo*:

- **Impacts us** — the changed/removed/deprecated surface is imported and used here. Cite `file:line`, name the required change.
- **Role mismatch** — common for web frameworks and client/server libs. A client SDK is unaffected by server-side form-parsing changes (and vice versa). State the role this repo plays.
- **Not used** — the surface exists in the library but the repo never touches it. Safe.
- **Opportunity** — a new API or default that would simplify or improve existing code here; point at the adoptable code.

Be skeptical of the PR's own auto-generated migration notes (cubic / Dependabot summaries). They address the library's general audience, not this repo — verify each against the code rather than repeating it.

### 6. For large grouped bumps

Fan out: one analysis pass per package (steps 2–5), then synthesize. Breadth must not dilute grounding — a "not used" verdict still requires the grep that proves it. If the only way to cut transitive-bump noise is upstream, say so and whether pinning is worth it.

## Notes

- Pairs with PR-review skills — this one answers "what does this bump mean for us", not "is the diff well-written".

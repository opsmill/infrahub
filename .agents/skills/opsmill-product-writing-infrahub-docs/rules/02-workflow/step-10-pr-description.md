# Step 10 — Generate PR description ★

Draft a slimmed-down summary as the PR body, on the repository's own PR template. [Which template sets the sections](#which-template-sets-the-sections) below says how.

[no-customer-pii](../01-principles/no-customer-pii.md) applies to the PR body as strictly as it applies to the docs. Docs PRs are public. Write the requirement, not who asked for it: no customer or prospect names, no people, no quotes from calls or transcripts, no real hostnames or addressing, no links to internal customer-specific pages. The two parts that leak most are "What needs reviewer attention" (where sourcing rationale lives) and "Open questions for the reviewer or SME" (where "flagged on the <Customer> call" gets typed without thinking). Check both before presenting the draft.

## Write the description in plain English

The PR body is read by a reviewer who wants to know what changed and whether it is right. Write it
the way you would write the docs.

**Do this:**

- State findings, not the search that produced them. "REST accepts `at` only on stored queries,
  artifacts and transformation endpoints (`api/dependencies.py:77`)" — not an account of how you
  came to check. The checks you ran are findings in their own right and go in the verification
  section, by name, method and count.
- Give a `file:line` reference for every product-behavior claim.
- Use literal verbs and the product's own terms, the same as on the page.
- Put open questions in their own section, each one a specific ask addressed to whoever can answer
  it.
- Say what is out of scope and why, so it does not read as an oversight.
- Say what was verified and how: each check by name and method, both walks from
  [checking-prose](../01-principles/checking-prose.md) by their counts and path, and the rule files
  read during the work.
- List everything the [Step 2](step-2-audit.md) audit found that the agreed scope did not cover, with
  the reason it was left. "Out of scope" is cheaper to write than a fix and looks tidier than
  admitting something was skipped, so the reader of the pull request gets the list rather than the
  tidy version.

**Leave out:** figurative verbs, narration of the writing process, headings such as "Found while
working", any sentence that would be equally true of any pull request, and self-assessment of the
work's quality.

For a worked reference, `opsmill/infrahub#10334` was rewritten to this standard. Its content (what
changed, why the structure changed, source material, facts verified against the implementation,
reviewer feedback, open questions, out of scope, verification) transfers to most docs PRs. Place
that content under the repository template's headings, as the mapping below shows.

★ **Gate**: present the draft PR description to the user. They approve or edit. **Do not commit until approved.**

## Which template sets the sections

The PR template is defined in one place: **the repository's own PR template sets the sections, and
this file says what content goes into them.** The opsmill-product `pr` skill also lets the repository
template win. [Step 11](step-11-lint-commit-push.md) hands it this body as approved and tells it not
to apply its own template. After `pr` opens the PR, check that the published body matches the
approved one.

1. Read the template from the base branch when you draft, not from memory. In Infrahub main it is
   `.github/pull_request_template.md` (lowercase). Other repositories may use
   `.github/PULL_REQUEST_TEMPLATE.md` or a `.github/PULL_REQUEST_TEMPLATE/` directory.
2. Use its headings, in its order. Replace its HTML comments with content; do not leave them in the
   body.
3. Put the docs content listed below under the heading it maps to.
4. If the repository has no PR template, use the headings in the example below as they are.

The example below fills the Infrahub main template as it stood when this file was written. If the
repository template has changed since, its headings win and the content mapping still applies.

| Content this skill requires | Where it goes in the Infrahub main template |
|---|---|
| What the change does for the reader, and the pattern | `# Why` |
| Out of scope (deferred), including everything the Step 2 audit found that the agreed scope did not cover | `# Why`, as the non-goals |
| Page outline or before/after table, sidebar placement, content changes, what stayed the same | `## What changed` |
| What needs reviewer attention | `## How to review` |
| Open questions for the reviewer or SME, one checkbox each | `## How to review` |
| Build and preview commands, and the verification with counts | `## How to test` |
| Moved URLs and how they still resolve | `## Impact & rollout`, as backward compatibility |
| The template's checklist | `## Checklist`, kept as the template has it |

## PR description template

````markdown
# Why

[What a reader of the docs could not find or do before this change, in one to three sentences.
Then what they can find or do after it.]

Pattern: <single-page merge / hub + spokes / tutorial extraction / split / section-wide restructure>.

Out of scope (deferred):

- [Cross-section content references to add elsewhere]
- [Anything the Step 2 audit found that the agreed scope did not cover, with the reason it was left]
- [Work deliberately held for a separate PR, with the reason, for example "the `--set location=DC1` example in `manage-from-cli.mdx` is wrong (`InfraDevice` has `site`); held back because it needs the CLI owner to review." Naming it here stops it reading as an oversight, and gives the reviewer the choice to pull it in.]

Closes <#issue> (delete this line when there is no issue)

## What changed

[For new feature docs: show the full page outline so the reviewer understands what was added before they open a single file. Include the sidebar placement, each file with its Diátaxis quadrant, and a one-sentence description of what it covers. This is the outline the user approved at Step 3 — reproduce it here.]

**Sidebar placement:** [Section > Category — e.g. Schema & Data > Graph Traversal]

| File | Type | Covers |
|---|---|---|
| `<folder>/overview.mdx` | Concept hub | [one sentence] |
| `<folder>/trace-a-path.mdx` | How-to | [one sentence] |
| `<folder>/analyze-dependencies.mdx` | How-to | [one sentence] |
| `reference/<slug>.mdx` | Reference | [one sentence] |

[For restructures: show a before/after table — old file → new file(s), noting what changed (rewritten, preserved as-is, moved to Academy).]

[For new feature docs, expand on the table above with a paragraph per page — what the page covers and any notable decisions (voice choices, content sourced from code vs spec, open issues flagged). Keep brief.]

[For a smaller update, a section-by-section list is enough:]

- **<Section name>**: <preserved as-is / rewritten as how-to / moved to Academy tutorial / etc.>

What stayed the same:

- All factual content preserved; no new claims invented
- [Any moved page's old URL, and how it still resolves]

## How to review

### What needs reviewer attention

[List the actual NEW prose the reviewer should read carefully. Skip anything that's verbatim extraction with only cross-link updates, because the reviewer can trust those.]

- **`<file>:<lines>`: <one-line description of new section/prose>.** <Brief rationale or where it came from, for example "Sourced from the Notion net-new content draft" or "Standard spoke 'Related' closer matching Generators/Transformations precedent.">

Everything else is carried over unchanged apart from updated links, so it is safe to skim.

### Open questions for the reviewer or SME

[Every unresolved content gap from step-2.7 becomes a checklist item here. Do not leave this section empty if there were unanswered missing-input questions. Each item should name the missing content, cite which comparable docs include it, and ask the SME to supply it or confirm it is out of scope.]

- [ ] **[Content gap name]** — [what is missing]. [Comparable OSS docs] cover this in [section/form]. Please supply the content or confirm this is intentionally out of scope for this release.

[Also include any open issues from the code accuracy pass — spec vs. implementation discrepancies, unverified labels, feature names that differ between announcement and UI, etc.]

- [ ] **[Discrepancy name]** — [announcement says X, code says Y]. Please confirm which is canonical.

## How to test

```bash
<build command from Step 0.5>     # Infrahub main: cd docs && npm run build
<preview command, if the repo has one>   # Infrahub main: npm run serve, then http://localhost:3000
```

Verification:

- Build: <passed, or not run and why>
- Lint: <pending, filled in at Step 11>. At Step 11, replace this with each tool by name and its result: Vale, markdownlint, the manual word check. A tool that did not run is named as not run.
- Step 9 audit: each pass by name: factual, placement, customer data, voice failure modes, terminology, corrections ledger, overview page content, thin input
- Subject walk: <N> sentences listed, <M> rewritten. Verb walk: <N> verbs listed, <M> replaced. Both in `dev/specs/docs/<slug>.checks.md`, uncommitted, available on request
- Rules read: <every rule file read during the work, by name>

## Impact & rollout

- **Backward compatibility:** <old URLs and how they resolve through redirects, or "No URLs changed">

[Delete the other items that do not apply. A documentation-only change usually has no performance, configuration or deployment item.]

## Checklist

[Keep the repository template's checklist as it is. Tick only what was done. For a documentation-only change, leave the changelog box unticked and add "not needed: documentation-only change" after it (Step 11). Leave "I have reviewed AI generated content" for the user to tick.]

````

> **Other repos:** use the build and preview commands found at [Step 0.5](step-0.5-detect-repo.md). If the repository has no preview command, leave that line out. Drop the redirects line if Step 7 did not apply.

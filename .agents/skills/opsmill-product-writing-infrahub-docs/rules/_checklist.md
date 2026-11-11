# Self-review checklist

On a docs-only update, a page went to a PR body as "verified" after Vale, markdownlint and the build
passed. It still lacked a Python SDK tab, lacked a branch-merge case, carried a false sentence on the
reference page, and had eight sentences whose subject could not perform the verb. Each of those is
covered by a rule file that was never opened. This list names every rule a page is checked against,
one line each, so the Step 4 self-review and the Step 9 audit can see which ones they have not
applied yet. Each line is a reminder, not the rule. The method is in the linked file, and you must
have read that file ([Required reads](../SKILL.md#required-reads)) before you tick its line.

## Tick these at Step 4, for every new or rewritten paragraph

Every file linked in this section is read by the end of the Draft phase. A line that starts with
"When" applies only in that case.

### Who acts, and what the words mean

- [ ] The subject of each sentence can perform its verb; the reader, Infrahub, or a state acts, never a version or a page: see [actors-and-causality](01-principles/actors-and-causality.md)
- [ ] Both walks, subjects and verbs, are written to the checks file with their counts: see [checking-prose](01-principles/checking-prose.md)
- [ ] The page reads as an experienced practitioner explaining the product, read through once for naturalness: see [checking-prose](01-principles/checking-prose.md)
- [ ] Tables are checked as prose: headers and cell values: see [checking-prose](01-principles/checking-prose.md)
- [ ] No pattern from the failure list remains: see [failure-modes](01-principles/failure-modes.md)

### Voice, openings and depth

- [ ] The prose meets the standard at the top of [voice-and-tone](01-principles/voice-and-tone.md): concrete, no marketing register, links inside sentences that say what is on the other side
- [ ] Page titles follow the title rule: see [voice-and-tone](01-principles/voice-and-tone.md)
- [ ] The page and each section orient the reader before implementation detail, and the page does not open with "use": see [right-altitude](01-principles/right-altitude.md)
- [ ] A mechanism stays only where it changes what the reader does: see [explain-and-describe](01-principles/explain-and-describe.md)
- [ ] Numbered steps appear only in dependency-ordered how-to guides: see [steps-vs-sections](01-principles/steps-vs-sections.md)

### Terms, facts and tabs

- [ ] Infrahub terms are capitalised as the product names them, and no synonym changes a meaning: see [product-terminology](01-principles/product-terminology.md)
- [ ] Every operation of the domain is covered or named as out of scope, including the branch-merge case: see [domain-lifecycles](04-infrahub/domain-lifecycles.md)
- [ ] Each GraphQL example has its Python SDK tab, or a placeholder when the SDK equivalent is unknown: see [Step 4](02-workflow/step-4-create-files.md)
- [ ] Interface tabs and their order match the sibling pages: see [Step 4](02-workflow/step-4-create-files.md)

### Page shape and placement

- [ ] When the page introduces a capability: it has the five parts of the content model: see [overview-page-content](03-patterns/overview-page-content.md)
- [ ] Files sit where the agreed outline and the navigation map put them: see [docs-navigation-map](04-infrahub/docs-navigation-map.md)
- [ ] When a tutorial is in scope: it passes the scenario-shape test: see [tutorial-shape-test](01-principles/tutorial-shape-test.md)

### User corrections and customer data

- [ ] Every correction in the ledger still holds after the last rewrite: see [corrections-ledger](01-principles/corrections-ledger.md)
- [ ] No customer or personal data in the prose, code samples or screenshots: see [no-customer-pii](01-principles/no-customer-pii.md)

## Tick these at Step 9, after reading the Ship row

These link to files in the Ship row of the Required reads table, which is read after Step 4.

- [ ] Every factual claim, example, opening and summary sentence has a source in the code or the docs: see [audit-rigor](01-principles/audit-rigor.md)
- [ ] A claim that names more than one interface has a source for each one: see [Step 9](02-workflow/step-9-pre-pr-audit.md)
- [ ] Any deviation from the agreed outline was raised with the user and written into the outline: see [spec-drift](01-principles/spec-drift.md), [gate-discipline](01-principles/gate-discipline.md)
- [ ] No customer or personal data in the branch name, commits or PR body: see [no-customer-pii](01-principles/no-customer-pii.md)
- [ ] The Step 9 audit ran every pass and its report cites both walks by count and path: see [Step 9](02-workflow/step-9-pre-pr-audit.md)

## Tick this at Step 10, when the PR body is drafted

- [ ] The PR body follows the repository's PR template and carries the verification counts and the rules-read list: see [Step 10](02-workflow/step-10-pr-description.md)

## Tick this at Step 11, after the lint tools have run

- [ ] Every lint tool ran, or is named as not run, and the lint line in the PR body holds the results: see [Step 11](02-workflow/step-11-lint-commit-push.md)

# Rule sections

Which of these files to read before each phase, per use case, is set by the
[Required reads](../SKILL.md#required-reads) table in SKILL.md.

## Index files

- [_checklist](_checklist.md): every rule a page is checked against, one line each with a link; the index for the Step 4 self-review and the Step 9 audit, not a replacement for the files
- [_template](_template.md): starting point for a new rule file

## 01-principles — repo-agnostic

Apply in every repo and every use case.

- [gate-discipline](01-principles/gate-discipline.md): stop at ★ gates, one per message; end each gate summary with the rules read; never recommend silently
- [right-altitude](01-principles/right-altitude.md): orient before implementation detail; the order of definition, capability and situation is a judgment call
- [explain-and-describe](01-principles/explain-and-describe.md): how much explanation a page carries, and when a mechanism earns its place
- [voice-and-tone](01-principles/voice-and-tone.md): the standard, economy vs shortness, the product's own terms, concrete language, marketing register, openers and titles
- [failure-modes](01-principles/failure-modes.md): the recurring failures, each paired with the fix on real text; checked at Step 4 and Step 9
- [checking-prose](01-principles/checking-prose.md): how to check the actor and literal-language rules, why grep cannot, tables, reporting what you checked
- [no-customer-pii](01-principles/no-customer-pii.md): no customer names, people, or environment data in docs, screenshots, commits, or the PR body
- [actors-and-causality](01-principles/actors-and-causality.md): who is the subject: the reader, Infrahub, or a state; never a version or a page
- [product-terminology](01-principles/product-terminology.md): which Infrahub terms are capitalised, and where a synonym changes the meaning
- [corrections-ledger](01-principles/corrections-ledger.md): user corrections survive rewrites; re-check the ledger after any restructure
- [tutorial-shape-test](01-principles/tutorial-shape-test.md): scenario-vs-feature test before keeping a tutorial
- [steps-vs-sections](01-principles/steps-vs-sections.md): numbered steps only for dependency-ordered how-to guides
- [audit-rigor](01-principles/audit-rigor.md): real read-through, source every claim, no invented content
- [spec-drift](01-principles/spec-drift.md): update the doc before implementing deviations

## 02-workflow — triage to PR

Three phases: **research** (0 – 2.7), **plan** (3), **build and ship** (4 – 11). All research completes before the outline; the outline is agreed before anything is drafted. Stop at every ★ gate. Step 0.5 locates the equivalent paths in a non-Infrahub repository — it changes paths, not which steps run.

- [step-0-triage](02-workflow/step-0-triage.md) ★: ask what kind of work it is, decide which kind it is yourself, name it to the user, route the outline
- [step-0.5-detect-repo](02-workflow/step-0.5-detect-repo.md): Infrahub-main defaults, or detect the equivalents by reading the repository
- [step-1-preflight](02-workflow/step-1-preflight.md): branch, clean tree, baseline build
- [step-2-audit](02-workflow/step-2-audit.md) ★: read source pages and neighbours; read the exemplars closest to the page you're writing
- [step-2.5-spec-review](02-workflow/step-2.5-spec-review.md) ★: when a recommendations doc exists, audit it against the skill rules
- [step-2.7-content-audit](02-workflow/step-2.7-content-audit.md) ★: research how comparable products solved it; verify facts against code; produce the gap list
- [step-3-outline](02-workflow/step-3-outline.md) ★: recommend pattern + outline, built from all Phase 1 research
- [step-4-create-files](02-workflow/step-4-create-files.md): draft per chosen pattern, match interfaces
- [step-5-sidebar](02-workflow/step-5-sidebar.md): update `sidebars.ts` (or repo equivalent)
- [step-6-build-verify](02-workflow/step-6-build-verify.md): `npm run build` (or repo equivalent)
- [step-7-redirects](02-workflow/step-7-redirects.md): Infrahub-main only; skip for repos without a redirects mechanism
- [step-8-cross-reference](02-workflow/step-8-cross-reference.md): find inbound references, decide fix vs defer
- [step-9-pre-pr-audit](02-workflow/step-9-pre-pr-audit.md) ★: read-through audit before opening the PR
- [step-10-pr-description](02-workflow/step-10-pr-description.md) ★: PR body on the repository's PR template, with reviewer-attention list, verification counts and rules read
- [step-11-lint-commit-push](02-workflow/step-11-lint-commit-push.md): Vale + markdownlint + word check; then commit/push/PR

## 03-patterns — structural choices

- [decision-rules](03-patterns/decision-rules.md): pick a pattern from the source content shape; what's in scope vs out of scope
- [single-page-merge](03-patterns/single-page-merge.md): Computed Attributes precedent
- [hub-and-spokes](03-patterns/hub-and-spokes.md): Groups / Profiles precedent; hubs end with an `## In this section` catalog
- [hub-and-spoke-scope](03-patterns/hub-and-spoke-scope.md): what belongs on a hub vs a spoke; how the "why" narrows between them
- [overview-page-content](03-patterns/overview-page-content.md): what belongs on a page that introduces a capability; learn from our exemplars and comparable products
- [comparison-page](03-patterns/comparison-page.md): "which of these do I use" pages; create-objects precedent
- [tutorial-extraction](03-patterns/tutorial-extraction.md): only when scenario-shaped
- [section-wide-migration](03-patterns/section-wide-migration.md): patterns on top of the standard workflow when migrating multiple features at once

## 04-infrahub — Infrahub-specific reference

Reference material for the Infrahub main repo specifically. Loaded when the skill is making placement decisions inside that repo.

- [docs-navigation-map](04-infrahub/docs-navigation-map.md): the docs.infrahub.app navigation tree, what each section is for, Diátaxis quadrant placement, cross-repo placement rules
- [domain-lifecycles](04-infrahub/domain-lifecycles.md): operations per Infrahub domain, checked against the code; read at Step 2.7 so a page's scope covers the whole lifecycle

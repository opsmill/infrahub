# Step 9 — Pre-PR audit ★

**Before opening the pull request**, do a thorough audit pass, so problems are fixed in the PR rather than in follow-up commits.

Read [audit-rigor](../01-principles/audit-rigor.md) first; this step puts it into practice. This audit runs on every use case ([what the smaller-update shortcut covers](../../SKILL.md#what-the-smaller-update-shortcut-covers)). The [self-review checklist](../_checklist.md) indexes the rules each pass below applies.

## Specific things to verify

### Factual / structural pass

**Check the final text against the source again, even though you verified the facts during research.** Between Phase 1 and here, the text has usually been rewritten several times, often in response to the user's own edits and rewording. Facts move, examples get shortened, and field names get changed while a sentence is being rephrased. What was verified was the earlier draft, not this one.

The failures this catches: a code example that lost a required field during a rewrite; a UI label that was paraphrased into something the interface does not say; a relationship or attribute name altered to read more smoothly; a claim about another product that drifted while the sentence around it was tightened. Re-open the schema file, the component, or the other product's docs — do not check from memory of having checked before.

- Re-read every new and modified file in this pull request.
- For each **factual claim**, find a source: the existing docs, the reference pages, schema definitions, or code. If a claim cannot be sourced, flag it.
- For a claim that names more than one interface, such as "`infrahubctl` and the Git integration" or "GraphQL and the SDK", find a source for each interface. Behavior found on one interface is not evidence for another. In testing, a sentence stating that the Git integration never deletes menu items came from a source about `infrahubctl` only, and the Git integration does delete them.
- Verify GraphQL mutations / queries match actual schema. Cross-check against:
  - `docs/docs/reference/schema/<feature>.mdx` if present
  - `docs/docs/reference/schema/attribute.mdx` for attribute kinds
  - Other feature docs that reference the same primitives
- Verify SDK examples are syntactically plausible. Compare against existing working examples in other feature pages.
- Verify all cross-links resolve to the correct page and section.
- Verify any new diagrams / tables / callouts are factually correct.
- For section-wide migrations: do a **user-perspective walk-through** as well — spin up the dev server, click through every new page in the order a real user would encounter them, look for orphan paragraphs / broken sidebar order / hub pages that read like stubs.

### Placement-verification pass

Confirm the files ended up where the agreed outline said they would:

- **File paths match** what was agreed at the Step 3 gate, or in the outline checked at Step 2.5.
- **Section placement matches the navigation map.** Each new file's top-level section in `docs/sidebars.ts` matches the [navigation map](../04-infrahub/docs-navigation-map.md)'s recommendation for that content kind. A how-to under "Reference" is wrong; a reference page under "Schema & Data" is wrong.
- **Diátaxis quadrant placement is correct.** Concepts on hub pages (not on spokes), how-tos on spokes (not on hub), tutorials in Academy (not as a spoke), reference content in the Reference section (not on the feature hub).
- **Multi-section content has one canonical home.** When a feature spans multiple sections, the canonical page is in the right section per the "When content could fit in multiple sections" rules, and the other sections have cross-links — not duplicated content.
- **Cross-repo overlap is honored.** For content involving satellites (Sync, SDK, Ansible, Nornir, infrahubctl, MCP), the canonical content landed in the canonical repo per the map. Main Infrahub gets a pointer, not a duplicate (or vice versa, depending on which repo owns the canonical home).

If anything has drifted from the approved outline, flag it the same way as factual findings — file path + what's wrong + suggested fix. Drift usually means either the outline was wrong (per [spec-drift](../01-principles/spec-drift.md), update the outline and re-confirm with user) or implementation diverged silently (move the file and update the sidebar).

### Customer-data pass

Run [no-customer-pii](../01-principles/no-customer-pii.md) over everything this PR touches: new and modified prose, code blocks, screenshots, the branch name, the commit messages, and the Step 10 PR body.

Grep the diff for the obvious carriers before reading: customer and prospect names from the inputs you were given, `@` in email form, real domains, and IP or ASN literals outside the RFC example ranges. Then read for the subtler ones: a requirement phrased as "requested by X", a quote lifted from a transcript, a hostname copied from a real device inventory, a screenshot with an org name in the breadcrumb.

Anything found is fixed in this PR, not deferred. Report it like the other findings, but do not print the offending value in full when reporting: give the file path, line number, and what kind of identifier it is.

### Voice-failure-mode pass

Lint tools and Vale won't catch these. The Step 4 self-review should have caught most — this pass is the safety net.

Re-read every new prose paragraph using the three-layer review in
[checking-prose](../01-principles/checking-prose.md) — meaning and causality, then naturalness, then
the mechanical checks. Include table headers and cell values.

Then read the page against [the patterns worth reviewing](../01-principles/failure-modes.md) and the
[standard at the top of voice-and-tone](../01-principles/voice-and-tone.md). Report findings with
file path and line number.

**Name the naturalness read separately in the report**, alongside factual accuracy and terminology.
Read the page continuously and ask whether it reads like an experienced practitioner explaining the
product, or like prose assembled from a style guide. Do not raise a finding merely because two
sections are shaped differently — that is usually correct.

### Terminology pass

Terminology drifts while sentences are reworded. Check the Infrahub terms against [product-terminology](../01-principles/product-terminology.md), and confirm identifiers, YAML keys and commands against the source rather than from memory.

### Corrections-ledger sweep

Make one pass over the [corrections ledger](../01-principles/corrections-ledger.md) alone: for each correction the user made, check that the final text still follows it — the reason behind it, not only the exact words. Rewrites and restructures tend to reintroduce corrected wording, and this is the last check before the user reads it again.

### Overview page content check

For every page that introduces a capability — a hub, a section overview, a new feature's main page — read it against the five parts of the [overview page content model](../03-patterns/overview-page-content.md) and name any that are missing or thin:

1. After the first two sentences, can the reader say what this is and whether it applies to them? A definition, a capability statement or a situation can all achieve that; opening on internals does not.
2. Does it describe the **situation** that makes the capability relevant — something a reader would recognize — or does it jump from the title to the mechanics?
3. Are the concepts limited to what the page's decisions require?
4. Do the paths carry enough to choose between them, in parallel shape? Try ruling one out using only what the page says; if you can't, neither can a reader.
5. Does it end with annotated links onward, rather than bare titles?

### Thin-input tell

Read each new page and ask: **is this mostly a restatement of code mechanics, with nothing on when to use it, why, or how it compares to alternatives?** That's the signature of docs drafted from thin input, and a missing part 2 above is usually the first place it shows. If so, do not ship it as-is silently — surface it: name the missing layer, say what input would fill it, and carry the gap into the PR description as an open issue (per [Step 2.7](step-2.7-content-audit.md)). The user decides whether minimal is acceptable; the audit's job is to make sure that's a decision, not an accident.

Report violations with file path + line number, same as the factual findings.

## Report format

Report findings with specific file paths + line numbers, e.g.:

- `groups/use-in-automation.mdx:54` — the claim that a Generator owns a `CoreGeneratorGroup` is wrong; per `generators/overview.mdx`, the SDK manages it automatically.

**Report what you checked, not a verdict.** Name each check and how it ran, and cite both layer-1
lists — the subject walk and the verb walk — by their counts and their path. "Report what you
checked, not a verdict" in [checking-prose](../01-principles/checking-prose.md) has the worked
report.

Never report a page as passing the actor rule or the literal-language rule on the strength of a grep,
and never report either walk without its count — a report with no count behind it means that walk
was skipped.

End the report with the "Rules read" line from [gate-discipline](../01-principles/gate-discipline.md).
The full list of rule files read during the work also goes into the verification part of the
[Step 10](step-10-pr-description.md) PR body.

★ **Gate**: present audit findings to the user. User decides which to fix in this PR vs defer. Fix the in-PR ones before continuing.

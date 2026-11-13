# Gate discipline

Stop and confirm with the user at every ★ gate. Implement only what the previous gate approved.

## The rule

When the workflow marks a step with ★, do the work for that step, present the output, and **wait for explicit user confirmation** before moving to the next step. Don't chain gates together. Don't "just keep going because it looks fine."

**One gate per message.** Do not fold the Step 0, Step 2 and Step 2.7 gates into the Step 3 outline gate. For a smaller update each gate can be a few lines, but each one is presented and confirmed on its own.

## Every gate summary ends with the rules read

A gate asks the user for a decision, and the user cannot see which rule files you read before you reached it. When an agent skipped half the rule files on a docs-only update, nothing in the gate summaries showed it: they asked for decisions, the lint passed, and the page went to a PR body as "verified" with eight sentences whose subject could not perform the verb. The user found it only by asking whether all the rules had been loaded.

So end every ★ gate summary with one line that lists each rule file read since the previous gate, by path under `rules/`:

> Rules read since the last gate: `02-workflow/step-2-audit.md`, `02-workflow/step-2.7-content-audit.md`, `04-infrahub/domain-lifecycles.md`, `01-principles/no-customer-pii.md`, `01-principles/corrections-ledger.md`

At the first gate, list what you read since the skill started. If you read nothing new, write "none". Compare the line with the [Required reads](../../SKILL.md#required-reads) table for the phase you are finishing. A file that the table requires and the line does not list is named with the reason it was not read, the same way a skipped step is named.

**A gate summary without this line is not a gate summary.** Do not ask the user to confirm until it is there.

## Why it matters

Docs work is iterative. A single wrong call at Step 3 (pattern decision) cascades into wrong file layouts at Step 4, wrong sidebar at Step 5, wrong redirects at Step 7. Catching it at the gate costs one message; catching it at PR review costs a re-do.

## Meta-rule: surface every recommendation, and never recommend silently

When implementation or spec review surfaces a change beyond what was already agreed — like merging two pages into one, adding a missing spoke, renaming a label, restructuring a sub-category — **present the recommendation to the user with rationale and wait for a decision before implementing.**

The recommendations doc (or the approved outline) is the canonical spec. Deviations get explicit approval, not silent application.

What this looks like in practice:

1. You hit a finding (e.g. "Git Integration category has no clickable hub link")
2. Present it to the user with rationale
3. User decides: yes fix it / no leave as-is / different approach
4. If yes, update the recommendations doc to reflect the new spec
5. Then implement against the updated doc

Update the doc when the work diverges from it, so it stays the one canonical spec and stays reviewable. **Do not quietly diverge from the doc.** An undocumented deviation means the reviewer can no longer trust that the doc describes what shipped.

## Compliant

- "Step 2 audit complete. Here's what I found: \[summary\]. Rules read since the last gate: \[files\]. Confirm and I'll proceed to Step 3."
- "I noticed the recommendations doc lists 3 spokes but `create`, `update`, and `delete` operations all look like obvious spokes that are missing. Want to add them to the spec, or leave as-is?"

## Non-compliant

- Step 2 audit complete → immediately proceeds into Step 3 outline without surfacing the audit.
- One message presents the triage, the audit, the comparable-docs findings and the outline together, and asks for a single confirmation.
- A gate summary with no "Rules read" line.
- Finds a missing spoke during drafting, silently adds it, doesn't mention it.
- "I'll just make a small structural change" without checking.

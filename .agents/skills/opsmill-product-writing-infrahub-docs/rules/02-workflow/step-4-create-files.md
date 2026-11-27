# Step 4 — Create new files

## Contents

- [Before drafting](#before-drafting)
- [While drafting](#while-drafting)
- [Orient the reader at the start of a section](#orient-the-reader-at-the-start-of-a-section)
- [Ground examples in recognizable work](#ground-examples-in-recognizable-work)
- [Keep the mechanism that changes what the reader does](#keep-the-mechanism-that-changes-what-the-reader-does)
- [After drafting (self-review, before the user sees it)](#after-drafting-self-review-before-the-user-sees-it)
- [After ANY rewrite or restructure — re-apply the corrections ledger](#after-any-rewrite-or-restructure--re-apply-the-corrections-ledger)
- [GraphQL examples and SDK tabs](#graphql-examples-and-sdk-tabs)
- [Screenshots](#screenshots)
- [Pattern-specific instructions](#pattern-specific-instructions)

Follow the chosen pattern. For section-wide migrations, do this **one feature at a time** with a build verification between each — see [section-wide migration](../03-patterns/section-wide-migration.md).

## Before drafting

0. **Re-open the source material for the section you are about to write.** The outline is an index, not the content — follow the links it records back to the briefs, transcripts, research, and approved recommendations, and work from those rather than from the outline's summary of them. This is the step most often skipped, and skipping it is what produces a page of accurate assertions with no reasoning behind them. See "Draft from the sources, not from your summary of them" in [Step 2.7](step-2.7-content-audit.md), which also sets out what counts as validated input — including recommendations you made that the user approved.
1. **Read [voice-and-tone](../01-principles/voice-and-tone.md) end to end.** The standard at the top is what to write towards; the rules below it catch the common failures. Read [actors-and-causality](../01-principles/actors-and-causality.md) with it — who acts in a sentence is the rule most often broken.
2. **Open a recently-merged feature migration page in the same docs section** for tone calibration. Don't open Groups or Profiles for voice — they're structural precedent, not voice precedent (see SKILL.md "Reference precedent" note).
3. **Pick the page title up front per the title rule.** Imperative form for tasks ("Create a sync project"); noun-phrase for reference and concept pages. Picking the title first forces clarity on what kind of page you're writing.
4. **Match the interfaces shown in the existing guide / tutorial.** Look at the existing guide and tutorial for that feature and preserve the same set of interface tabs, reusing the same running example. Do **not** reduce a multi-interface task to GraphQL-only because it's faster to write.

   **Tab order:** (a) if sibling pages in the same section already show this interface set, match their order exactly — consistency within a section beats any global preference; (b) if there is no sibling precedent, open 2–3 recent pages that use `groupId="method"` (for example `groups/create.mdx`: web → graphql → sdk) and follow the dominant order, with the web interface first and `default`; (c) if the page introduces a new interface combination with no precedent (for example adding `infrahubctl` to the set), propose the order at the outline gate instead of inventing it silently. Always use `<Tabs groupId="method" queryString>` so the reader's choice persists across pages.

## While drafting

For every intro paragraph and every capability sentence, run the **mental-model check from voice-and-tone**:

- Would this paragraph open a page on FastAPI / uv / Stripe?
- Does it lead with capability, not implementation type?
- Is the reader addressed as "you" (or via imperative), not as "teams" or "operators"?
- If the product appears as the subject, is it a capability/mechanical statement (✅) or a value statement (❌)?

If the answer to any of those is no, rewrite before continuing. The check is faster than fixing the prose later in Step 9.

## Orient the reader at the start of a section

The opening of a section should make clear why the section is there. Depending on what the section
does, the clearest opening may be a definition, a practical rule, a when-to-use statement, a choice
between options, a direct instruction, or a statement of observable product behavior.
[right-altitude](../01-principles/right-altitude.md) owns the rule — the openings that work, the
"use" rule for page openings, and how specific a named situation has to be; this section is its
application to `##` sections.

Four openings from one page, each fitting its section:

> **Definition** — A computed attribute is a read-only `Text` or `URL` value calculated from data already modeled in Infrahub.
>
> **Choice** — Use Jinja2 when the value can be calculated from attributes on the same object and direct relationships.
>
> **Product behavior** — Infrahub recalculates a computed attribute when data used by its calculation changes.
>
> **Procedure** — Define a Jinja2 computed attribute directly on the attribute in your node schema.

These are different because the sections are doing different jobs. Do not rewrite them into a common
pattern for consistency.

What does fail is opening on the mechanism, so the reader has to work out why the detail is on the
page:

"The opening does not orient the reader" in [failure-modes](../01-principles/failure-modes.md) has
the worked pair.

## Ground examples in recognizable work

This is about what makes an example worth having, not about how many a page should carry or where
they go. When you use one, it should answer a question a network or infrastructure engineer would
actually ask rather than only demonstrating the syntax — "which services depend on this circuit",
"which interface attributes changed during the incident", "which devices are missing a platform".
The reader should recognise their own work in it.

An example earns its place where the reader is choosing between options or about to do something.
An opening establishes the capability and the situation, and a list of example questions there
competes with that job rather than supporting it.

## Keep the mechanism that changes what the reader does

Keep a technical explanation when knowing it helps the
reader predict behavior, choose between options, understand a result, troubleshoot, or understand a
limit — see [explain-and-describe](../01-principles/explain-and-describe.md) for the shape and the
one case where the rule comes before the mechanism.

## After drafting (self-review, before the user sees it)

**This pass runs before the prose is shown to the user, on every revision — not only before the build.** Its old trigger was the build step, which meant a draft pasted into chat skipped it entirely and reached the user unchecked. Any new or rewritten prose gets scanned, whether it is the first draft of a page or one paragraph changed on request.

Run the three-layer review from [checking-prose](../01-principles/checking-prose.md): read for
meaning and causality — including both walks, the subjects and the verbs — then read the page through
for naturalness, then run the mechanical checks. Tables are prose — check headers and cell values
too.

The naturalness layer is the one most often skipped, and it is what catches a page that satisfies
every rule and still reads as generated: several sections opening the same way, second person that
has become repetitive, an imperative where a definition was clearer, a sentence made more awkward in
order to fix an actor. If a sentence is accurate, clear and natural, leave it alone.

Then ask the three absence questions, which the list below cannot catch because they are about what
is missing:

- Does the page name the situation that makes the capability relevant?
- Does every `##` opener and every tab opener say what the section is for?
- After reading it, can the reader decide something they could not decide before?

Then check each paragraph against [the recurring failure
modes](../01-principles/failure-modes.md). That table is the single
copy — it names what to write instead of each failure.

Rewrite each violation in place. This is cheaper than catching it in Step 9 (pre-PR audit) and much cheaper than catching it in PR review.

Finish by going down the [self-review checklist](../_checklist.md), which names every rule in one line. It is an index of the rules this pass applies, so a rule is not missed; the checks themselves are in the files it links. A smaller update runs this whole pass ([what the shortcut covers](../../SKILL.md#what-the-smaller-update-shortcut-covers)). Tick the lines under the Step 9, Step 10 and Step 11 headings at those steps, after you have read their files.

## After ANY rewrite or restructure — re-apply the corrections ledger

When a draft is restructured — sections reordered, a table turned into prose, content regrouped — check the new text against every correction the user has made this session **before** showing it to them. See [corrections-ledger](../01-principles/corrections-ledger.md). Wording the user already rejected tends to return during a restructure, because rewriting from the ideas produces the same phrasing again. The fact that the user has already corrected this page means you need to check more carefully, not less.

## GraphQL examples and SDK tabs

When you write a GraphQL query example, ask: does the Python SDK expose an equivalent method for this operation? If yes, wrap both in a `Tabs` block rather than showing GraphQL alone, ordered per the tab-order rule above (match siblings; when in doubt, follow `groups/create.mdx`).

The signal that SDK coverage exists: the operation touches `InfrahubClient` or a related client class in the SDK. Check `docs.infrahub.app/python-sdk` or ask the user if unsure. Don't leave a GraphQL-only example when the SDK equivalent exists and a reader following the how-to would reasonably want both.

If the SDK equivalent is unknown or not yet documented, add a placeholder rather than silently omitting it:

```mdx
<Tabs>
  <TabItem value="graphql" label="GraphQL">
    {/* your query here */}
  </TabItem>
  <TabItem value="sdk" label="Python SDK">
    {/* SDK equivalent — documentation in progress */}
  </TabItem>
</Tabs>
```

## Screenshots

Screenshots are a maintenance burden — every UI change can break them. Default to good prose. Only add a screenshot when the visual output genuinely cannot be described in words and a reader would stall without seeing it.

That bar is high. Most UI steps don't meet it. "Select **Find Paths**" doesn't need one. "In **Source Object**, search for and select the starting object" doesn't need one. These are clear from the text.

**The rare cases that do meet the bar:**

- A complex visual output (a rendered graph, a diff view, a diagram) where the structure itself is the point and prose can't substitute
- A UI state that is genuinely hard to locate without a visual anchor — for example, a non-obvious right-click menu that a reader might not discover on their own

When you identify one of these, add a placeholder comment and flag it in the PR description rather than blocking the draft:

```mdx
{/* screenshot: [what to capture and why prose isn't sufficient] */}
```

If in doubt, leave it out. A placeholder that never gets filled becomes a comment in the source forever. Err toward fewer screenshots, not more.

## Pattern-specific instructions

- [Single-page merge](../03-patterns/single-page-merge.md)
- [Hub + spokes](../03-patterns/hub-and-spokes.md)
- [Tutorial extraction](../03-patterns/tutorial-extraction.md)

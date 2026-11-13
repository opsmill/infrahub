# Spec drift during implementation

When drafting reveals a gap in the agreed outline — a missing page, two pages that should merge, a hub with no clickable link, a page put in the wrong place — **update the outline first, then build against the updated version.**

## Why

The outline stays the single description of what is being built, and any change to it is visible. Editing it a few times during a large migration is normal.

## The pattern

1. You hit a finding (e.g. "Git Integration category has no clickable hub link")
2. Per [gate discipline](gate-discipline.md), present it to the user with rationale
3. User decides: yes fix it / no leave as-is / different approach
4. If yes, update the outline to reflect the decision
5. Then implement against the updated doc

## What this prevents

Quiet divergence from the doc breaks the "one canonical spec" property and makes future review harder. The reviewer can no longer trust that the doc reflects what shipped.

# Tutorial scenario-shape test

Before keeping a tutorial, verify it teaches a coherent end-to-end scenario someone would actually want to learn.

## When to apply

If the chosen pattern preserves an Academy tutorial (Tutorial extraction or Split), run this check before keeping it.

## The test

Read the source guide and ask: *does this teach a coherent end-to-end scenario someone would actually want to learn — routers/switches at scale, modeling a service, onboarding a new team — or is it the same content as the existing guide with sequence numbers stuck on it?*

- **Scenario-oriented** → keep the tutorial. It earns its sidebar slot.
- **Feature-oriented** → drop the tutorial from this PR. Add a row to the [Docs content queue](https://app.notion.com/p/8e29c383844142919545717d2b89e5d9) in Notion that describes the scenario rewrite needed. Fill it in as [How to fill in a row in the Docs content queue](https://app.notion.com/p/3f4228b83025819d93a1deb4177e7f0c) describes.

**Ship a tutorial only when it follows a scenario a reader would recognise, and do not ship feature-oriented tutorials.** A feature-oriented walkthrough belongs in a how-to, where it earns its place.

## Tutorial-shape signals (at audit time)

A guide is tutorial-shaped if it has:

- Step 1 / Step 2 / Step 3 headings
- A single running example used throughout
- A "Next steps" closer
- Linear narrative arc

Those signals tell you the guide *could* extract to Academy. The scenario-shape test above tells you whether it *should*.

## Precedent

The Profiles tutorial was dropped on PR #9114 review for exactly this reason — it was feature-oriented (sequence numbers on Profiles operations), not scenario-oriented.

# What belongs on a hub, and what belongs on a spoke

[hub-and-spokes](hub-and-spokes.md) covers the file structure and the sidebar wiring. This is about
the content: how much context each page carries, and where the boundary sits.

**The division:**

> A hub explains why the capability matters and how its major concepts fit together.
> A spoke explains when this particular operation matters and how to use it.

A spoke still needs a "why". The difference is that its "why" narrows to the operation in front of
the reader.

| Page | The question its "why" answers |
|---|---|
| Hub | Why does immutable history matter? |
| Spoke | When should I compare two timestamps instead of querying one? |

**A spoke does not re-establish the value of its hub's capability.** By the time a reader reaches
`DiffTree`, the useful context is which operation to choose, not why the feature exists.

## Hub pages

A hub introduces a capability or a set of related concepts. It covers:

- what the capability does;
- why and when it matters;
- the main things you can accomplish with it;
- the mental model needed to understand it;
- how the major concepts relate;
- where to go for specific tasks.

A hub carries more of the broad "why" than a spoke does, expressed through concrete network or
automation work.

**Suggested progression, not a template:**

capability → situations where it matters → what you can accomplish → core concepts → the mechanism
that explains behavior → paths to the detailed tasks

The order is not fixed, and a hub can open with a definition where that is what the reader needs
first — see [right-altitude](../01-principles/right-altitude.md).

A hub generally stops before procedures, API syntax, configuration steps, edge cases and reference
behavior. Once a spoke exists, the hub states the core behavior and links to it:

> By default, queries return the latest data on the selected branch. Set a time when you need the
> values and relationships that were valid at an earlier timestamp.
>
> See Query historical data for the available interfaces, comparing two timestamps, supported time
> formats, and branch history limits.

## Spoke pages

A spoke covers one capability, operation, workflow or behavior. It covers:

- what you can accomplish;
- when you would do it;
- what inputs or choices decide the result;
- how to perform the task;
- what Infrahub does in response;
- what result to expect;
- which option to choose when there are alternatives;
- the defaults, limits, errors and edge cases that change how you use it.

**Suggested progression:**

capability → when it matters → operating model → procedure → expected behavior → limits and
reference

A structure that works, with no requirement that every page has every part:

1. Capability and when it matters
2. The mental model the task needs
3. How the behavior works
4. Perform the task
5. Choose between approaches or interfaces
6. Expected behavior and limits
7. Related pages

## Orient before the mechanics

Say which decision a technical section helps the reader make, then go into the mechanics.

> Use a diff when you need to identify which objects or attributes changed between two timestamps.

Then `DiffTree`. What to avoid is restating the feature's value before every section, which makes the
page read as a series of overviews.

## Resolve the nearby choices that affect the task

A spoke should distinguish neighboring Infrahub mechanisms where a reader could reasonably pick the
wrong one for the same apparent goal. This is the kind of decision a spoke exists to settle, and it
usually takes three or four lines.

Cases that have come up: a computed attribute against `display_label` against `human_friendly_id`; a
Generator against a Transformation; a Profile against an Object Template; a timestamp comparison
against a Proposed Change diff.

Add it where the distinction changes how the reader implements the task. Not merely because related
features exist.

## The scope check

Two questions at the pre-PR audit:

- Is there architectural explanation on this spoke that belongs on the hub or a concept page?
- Is there procedural or reference material on this hub that belongs on a spoke?
- Is there an adjacent Infrahub mechanism a reader could reasonably confuse with this one, and does
  the distinction change the implementation? If so and the page does not cover it, that is a gap.

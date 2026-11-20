# Orient before implementation detail

Early in a page, give the reader enough to know two things: what the capability is or what they can
do with it, and when it is relevant to their work. **The order is yours to choose.**

A definition is often the clearest opening for a concept or a feature page. A capability statement
can be better for a task-oriented page. A situation can be the best entry point where the feature is
already familiar.

The distinction that matters is orientation against implementation detail. Do not make a reader work
through storage internals, API parameters, or architecture before they know why any of it matters to
them.

## Two openings, both of which work

**Definition, then the deciding condition:**

> A computed attribute is a read-only `Text` or `URL` value calculated from data already modeled in
> Infrahub. Use a computed attribute where that value should stay in step with the attributes and
> relationships it is built from, rather than being entered and maintained separately.

The first sentence says what the thing is. The second says when you would want one. The
implementation choice — a Jinja2 template or a Python Transformation — comes after.

**Capability, then the situations:**

> You can query infrastructure data at previous points in time and compare how it changed between
> them. Use queries with a timestamp to investigate incidents, verify changes during a period,
> answer audit questions, and inspect how objects and relationships differed at an earlier time.

Both orient the reader. Neither is the canonical pattern.

## An opening that does not work

Accurate, and useless to someone who has not yet decided they need it:

> Every read you make in Infrahub already carries a point in time.

It leads with the mechanism. Nothing in it tells a reader whether the page is for them.

## Do not open a page with the word "use"

"Use X to…" gives an instruction to someone who has not yet been told what X is, and it makes every
page start with the same sentence. What a thing is and what it is for are closely related — say what
it is, and move into what it is for.

This is about the first sentence of a page. "Use" is fine further down, and fine as a section
opener.

## Name cases specific enough that a reader can tell whether they are in one

"Use this when you are deciding what to create as you go" excludes nobody, so it helps nobody
choose. A reader should recognise their own environment, or rule themselves out, and what carries
that is concrete circumstance: the scale, the workflow, the configuration, the thing that goes wrong
in it.

| Situation missing | Situation named |
|---|---|
| "Regeneration after a merge is narrowed to the affected definitions." | "On an instance where one artifact definition targets thousands of devices, merging a change to a single site previously regenerated every device's artifacts." |
| "Use object files for data that changes rarely." | "Use object files for the reference data your instance is built on: sites, roles, platforms, device types." |
| "Small changes." | "A single device, a few prefixes, or any change small enough to enter manually." |

Then say what it changes for the reader's work: what they wait for, what they can stop checking,
what they no longer repair manually. Explaining why a capability matters is part of the writing, not
an overreach — reason from the sources you have and write it. Where you have reasoned rather than
quoted, mark it so a reviewer can confirm the substance. See
[explain-and-describe](explain-and-describe.md) for how much of this a page is expected to carry.

## The check

Read the first two sentences and ask what the reader can decide from them. If the answer is "nothing
yet, I have to keep reading to find out whether this is for me", the opening is not doing its job.

## A common progression, not a template

Many pages move from orientation towards implementation:

**orientation → the decisions or mental model the reader needs → behavior → procedure → limits and
reference**

Treat that as the usual shape, not a required one. Skip, combine, or reorder the parts when another
shape explains the thing better. A page forced into a fixed sequence reads as generated, however
correct each part is.

## Why this needs stating at all

Reading code produces parameters, formats, and limits, because that is what code contains. A page
planned straight from an implementation review arrives as an index of verified facts, since that is
the shape of the research. The orientation layer comes from different sources — the problem sections
of a brief, a support conversation, an incident — and it has to be gathered deliberately or the page
will not have it.

See [explain-and-describe](explain-and-describe.md) for how much explanation a page should carry,
and [hub-and-spoke-scope](../03-patterns/hub-and-spoke-scope.md) for how the "why" narrows between a
hub and its spokes.

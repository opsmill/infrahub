# Overview page content — what to put on a page that introduces a capability

Applies to any page a reader lands on to find out what something is and how to approach it: a feature hub, a section overview, or the main page of a brand-new feature. The structural patterns say where files go; this is about what the page contains.

There is no single template, and imposing one produces interchangeable pages that fit no feature well. What these pages share is the set of questions they answer:

- What can I do with this?
- Why would I use it — what situation makes it relevant?
- What do I need to understand before I can decide anything?
- What are my options, and which one is mine?
- Where do I go next?

The shape that carries those answers depends on the feature. Work it out by reading pages that already solved a similar problem, in our docs first and then in comparable products.

## Read our own docs first — and read the closest one, not the newest one

Open two or three of these before outlining, chosen by what your page has to do. Each solves a different problem well:

| If your page… | Read | What to take from it |
|---|---|---|
| Presents two or three ways to do the same job | `graph-traversal/overview.mdx` | The cleanest choose-your-path hub we have: capability lead, a prose paragraph per mode, then a "When to use each mode" table plus concrete scenarios ("tracing connectivity between two devices while investigating packet loss"). 72 lines. |
| Presents four or more ways, or ways that differ in workflow | `objects/create-objects.mdx` | Grouping into named categories, a summary that lets a reader jump, and identical beats per option. See [comparison-page](comparison-page.md). |
| Introduces a feature made of several parts that work together | `events/overview.mdx` | Opens with what it's for and common uses, then an annotated catalog of the three parts, then how the flow fits together. |
| Introduces one feature with variants to choose between | `groups/overview.mdx` | Concept framing plus a "Types of groups" decision table; short, and it ends by pointing at the tutorial and the reference. |
| Fronts a section of several pages | `ipam/overview.mdx`, `schema/overview.mdx` | Compact concepts, then `## In this section` — the catalog format hubs use ([hub-and-spokes](hub-and-spokes.md)). |
| Covers a feature with genuine operational depth | `resource-manager/overview.mdx` | Pool types framed as use cases, allocation methods, and a "Best practices" section — how depth is organized when it's warranted. |

Also read one page as a **caution**: `generators/overview.mdx` is 311 lines of mostly execution mechanics. Accurate, and the reference material a Generator author eventually needs — but a reader arriving to find out whether Generators are for them has a long way to go. When your draft starts down that road, that's the signal to move depth onto its own page.

Prefer the page closest to your problem over the most recently merged one. For **voice**, though, still calibrate against a recent merge — the voice rules have moved since the older hubs landed.

## The part that is usually missing: why you would use it

Every page above says what the feature is and how it works. The one that varies is whether it says **what situation makes the feature relevant** — and that is the part readers need most and drafts most often skip.

Describe the reader's situation concretely, not the feature's benefits:

> ✅ "Some objects exist because other data does, and they have to stay correct as that data changes. Maintaining them manually means repeating the same work every time something upstream changes."
>
> ❌ "Generators save time and reduce manual errors." — a benefit claim; unsourced and unfalsifiable.
> ❌ "Generators let you automate object creation." — restates the feature name.

`graph-traversal/overview.mdx` does this with examples rather than assertions ("before a maintenance window", "while investigating packet loss") — naming a moment in the reader's work is usually stronger than describing a benefit.

**Look for it in the problem sections of your inputs, not the capability sections.** Mechanics can be read from the code; the situation cannot. Briefs carry it under headings like "current state and pain points", "alternatives", or "why teams struggle today" — and those are the sections a capability-focused reading skips, which is why drafts arrive without a why-layer even when the material was supplied. Read them before you draft this part, not only before you outline.

If nothing in your sources establishes the situation, write your best reading of it and label it for the feature owner to confirm ([Step 2.7](../02-workflow/step-2.7-content-audit.md), [Step 0](../02-workflow/step-0-triage.md)). Dropping the section is not the safe option: a page that goes straight from the title to the mechanics is the visible symptom, and it is a worse failure than a paragraph a reviewer has to correct.

## Explain and describe

This guidance moved to [explain-and-describe](../01-principles/explain-and-describe.md), because it
applies to every page that teaches, not only to overviews. Keeping it here meant a writer working on
a task page never reached it, and shipped an accurate page that helped nobody decide anything.

Read it before drafting any page. Orientation pages carry more of it than reference pages do, which
is the only part of it specific to this file.

## Then look outside for what we're missing

Our docs show how we handle a shape; comparable products show what we haven't thought to include. Benchmark against 2–3 for the feature class ([Step 2.7](../02-workflow/step-2.7-content-audit.md) has the class table — NetBox and Nautobot for source-of-truth features, Kubernetes for object management, Stripe for API surfaces).

Read them for structure and coverage, not prose: which sections do they include that our inputs don't cover? NetBox's [Populating Data](https://netboxlabs.com/docs/netbox/getting-started/populating-data/) orders methods simplest to most automated and steers with callouts; [Kubernetes Object Management](https://kubernetes.io/docs/concepts/overview/working-with-objects/object-management/) gives each technique identical subsections so they can be compared, and warns against mixing them. Both ideas transferred directly into `objects/create-objects.mdx`.

Bring the findings to the outline gate as recommendations with sources, split into what you can write accurately and what needs an answer from the feature's owner.

## When the options are the point

If most of the page is the choose-your-path part — four or more options, or options that differ in workflow rather than just interface — it isn't an overview with a list at the end, it's a comparison page. Follow [comparison-page](comparison-page.md), and check the paths discriminate: try ruling one out using only what the page says. If you can't, neither can a reader.

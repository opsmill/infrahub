# Comparison page — "which of these do I use?"

Use this when one page presents several alternative ways to do the same job, and the purpose of the page is to help the reader choose: ways to create objects, ways to install, ways to authenticate, ways to import data. It is not a hub, because it has no child pages of its own. It is not a how-to, because the reader goes elsewhere to do the task. None of the other patterns describe it.

**Example in our docs:** `docs/docs/objects/create-objects.mdx`. **Examples elsewhere:** [Kubernetes Object Management](https://kubernetes.io/docs/concepts/overview/working-with-objects/object-management/), [NetBox Populating Data](https://netboxlabs.com/docs/netbox/getting-started/populating-data/).

## How to structure it

1. **Group the options into three or four named categories.** A reader can keep three categories in mind; they cannot keep seven separate options in mind. Name the categories by what separates them from the reader's point of view — in `create-objects.mdx` that was *directly*, *from a file*, and *from a workflow*, which describes what starts the work. Listing many options with no grouping is the most common reason this kind of page does not work.
2. **Start with a summary of the categories.** One bullet for each: what it is, and when to use it, linked to its section. The reader chooses a category before scrolling. Check that the links match the heading IDs on the rendered page.
3. **Describe every option in the same three parts:** when to use it (two or three sentences), then an example or an explanation of how it works, then one link to read more. Describing each option the same way is what makes them comparable — once the reader has read one, they know what to expect from the others. An option with an example next to an option without one looks like a different kind of thing, which misleads the reader.
4. **Use one example throughout,** wherever the options genuinely do the same task. Showing the same object created four ways demonstrates that the result is the same, which four different examples cannot. Check every field of the example against the schema before writing it.
5. **End with what happens after the choice** — the consequences that apply whichever option the reader picked, such as branch behaviour, review, and metadata — then a Related section.

## Table, prose, or tabs

- **Tabs** are for one task done through different interfaces, where the inputs and the result are the same and the reader is choosing a tool. They are wrong for comparing approaches that differ in how they work, because tabs hide all but one option at the point where the reader is comparing them. On a comparison page, tabs can appear inside a single category — in `create-objects.mdx` the "directly" category contains four interface tabs — but never as the structure of the whole page.
- **A comparison table** is worth using only when the values in each cell are short, factual, and directly comparable. Kubernetes can use one because its cells read "Live objects", "Individual files", "Directories of files". If the useful content for each option is a full sentence, a table becomes prose squeezed into cells: use sections instead. Do not include both a table and per-option sections that repeat it — readers find pages harder to follow when the same information appears twice.
- **Prose sections** are the default, as in the NetBox page: one section per category, ordered from the simplest method to the most automated.

## What the content has to do

- **The "when to use it" sentences are the most important content on the page.** Each one should answer the same questions, so the reader can compare them: how many objects at a time, where the definition comes from, and whether it happens once or repeatedly. "Use this when you are deciding what to create as you go" does not help anyone rule an option out. "Use this for a single device, a few prefixes, or any change small enough to enter manually" does.
- **Group automated systems separately from interactive methods.** A Generator or a sync tool is not another way for a person to create one object, and listing them together confuses two different kinds of thing. Give them their own category, and explain **when the objects are actually created** — which event or command causes it — because a reader cannot guess that.
- **Every section must say what the option is for, not describe a property it has.** "Use object files for data that changes rarely" describes a property. Saying what keeping the file in Git gives you — review in a pull request, the ability to rebuild an instance, promotion between environments — and which data suits it, such as sites, roles, platforms, and device types, says what it is for.
- **Leave out options that do not exist yet.** A planned feature or an unwritten page produces a row that links nowhere, which is worse than not mentioning it.

## Read comparable docs before outlining this shape

This is the page type where other products' docs are most useful, so read two or three of them first ([Step 2.7](../02-workflow/step-2.7-content-audit.md)). Two ideas were taken directly from them: describing every option in the same way, from the Kubernetes page, and ordering the options from simplest to most automated, from the NetBox page.

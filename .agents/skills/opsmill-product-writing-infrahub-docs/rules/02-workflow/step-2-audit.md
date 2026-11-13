# Step 2 — Audit existing content ★

Read the source files completely before deciding what to change.

> **Other repos:** substitute the resolved docs root from [Step 0.5](step-0.5-detect-repo.md) wherever `docs/docs/` appears.

## Read

- Every page you are changing or replacing, in full.
- For a section-wide change, every page in the section, not only one feature.
- The two or three existing pages closest to what you are about to write, chosen with the table in [overview-page-content](../03-patterns/overview-page-content.md). These set the shape and the voice.

## Read the whole page, not only the part you were asked to change

Every section gets one question: does this still do its job? A single page is short enough that
this costs minutes, and it is the only way anyone finds out that the part nobody mentioned is the
weakest part of the page.

Record what you find as a list — the section, and what is wrong with it. That list is what the
scope options at [Step 3](step-3-outline.md) are built from. Anything the agreed scope does not
cover goes into the pull request ([Step 10](step-10-pr-description.md)) instead of being dropped.

What turns up this way: a comparison table whose rows say "lightweight" and "powerful", a section
written as a tutorial, a claim that is true of one code path and stated for both, a setting that
limits the feature and is documented nowhere.

## Summarise what you found

- **Each page** — headings, length, and what it covers well or badly.
- **Is any of it tutorial-shaped?** Step 1/2/3 headings, one running example throughout, a "next steps" closer, a linear narrative. If so it may belong in Academy rather than in the feature pages — see [tutorial-shape-test](../01-principles/tutorial-shape-test.md).
- **Inconsistencies and gaps** — report them and let the user decide. **Do not silently fix them**; a fix folded into a migration is invisible at review.
- **Inbound links** — `grep -rln '<feature-slug>' docs/docs/` to find pages linking to what you are moving. Step 8 acts on these.

## Use case 2 variant (new feature docs)

For new feature docs (no existing files), this step becomes "read related sections to calibrate tone." Pick 1–2 nearby pages in the section the new docs will live in, summarize their shape and voice, and use that as the template for the outline at Step 3.

★ **Gate**: present the audit to the user. Wait for confirmation before proceeding.

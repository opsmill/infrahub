# Reporting a structural pass

> Part of: `dev/guidelines/reviews/` | Related: [Structural Review](README.md), [Lenses](lenses.md)

## Header

State the reference frame, the commit pair the pass was run on, and the target branch as context
only. The target branch never carries a verdict.

## Findings

At most seven findings, ordered by cost of deferring: the number of sites that have to change
first, then the fan-in of the packages involved. Anything past the cap gets one line.

```markdown
### <n>. <title> (Lens <A|B|C|D>)

- **Evidence:** the compare line, `<file>:<line>` or `<pkg> → <pkg>`, with the number that crossed
- **Future scenario:** <concrete event>
- **Alternative:** <one or two sentences>
- **Cost of deferring:** <sites, packages, migrations, with counts>
- **Hand-off:** none | issue (`creating-issues`) | ADR (`opsmill-dev:creating-adrs`, `dev/adr/`)
```

An empty findings list is a valid result, as long as the frame is named and the comparison the pass
ran on is shown.

## Closing sections

- **Open questions:** one line each. A direction candidate with no reference frame lands here.
- **Positives:** edges removed, files shrunk, one line each.

Offer the hand-offs. Never open an issue or write an ADR without a yes.

## Anti-patterns

- A crossing with no future scenario is not a finding. Drop it.
- No number in the report that you did not read out of a command's output. Show the command.
- No timing or merge verdict, ever.
- No generic smells (naming, duplication, function length). Other passes own those.
- No direction finding on principles alone. Cite the frame, or ask a question.

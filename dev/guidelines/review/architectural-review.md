# Architectural review

> Part of: `dev/guidelines/review/` | Related: [Review passes](README.md), [Repository Organization](../repository-organization.md)

This pass reads a diff for the risks it adds to the shape of the codebase: a special case that will
be copied, a file that just took on a second job, an import that points the wrong way. It reports
risks and never decides.

## Scope

The pass produces risks with a scenario attached. It produces no PASS/FAIL, no merge or timing
verdict, no code change, and nothing posted on the pull request. Generic smells (naming,
duplication, function length) belong to other passes.

Judge the delta only. Pre-existing debt is out of scope, however visible it is from the diff.

## Reference frame

Name the frame at the top of the report, taking the first one that exists:

1. The project architecture docs: `dev/knowledge/`, `dev/adr/`, the `AGENTS.md` files.
2. The import graph the repository has today, measured on the base commit.
3. None. Then ask questions instead of judging.

Never invent a target architecture.

## Candidates and findings

Every crossing a lens turns up is a candidate. It becomes a finding only once a concrete future
event is attached to it, one that makes the crossing cost something. A crossing with no scenario is
dropped, not reported.

A new package in the diff gets the four lenses applied to its internals. Its placement is an open
question and an ADR candidate, not a finding.

## Lens A: N+1, solving the instance instead of the class

| Signal | Threshold |
| --- | --- |
| New or grown hardcoded kind set `{InfrahubKind.X, …}` | any |
| Dispatch branches on one discriminant (`kind`, `inherit_from`, `isinstance`) in one function | ≥ 3, or an existing ≥ 3 grows |
| `bool` mode flag added to signatures in one file | ≥ 2 |
| Extra pass or phase added to a sequence, hardcoded ordering | reading only |

Ask: what concrete event is N+1? What design absorbs that event with no new code? Count the sites
that have to change when it arrives: sets, flagged signatures, call sites, tests pinning the order.
Three or more sites is a high cost of deferring.

## Lens B: Size and responsibilities

| Signal | Threshold |
| --- | --- |
| File crosses size | base < 500 LOC ≤ head |
| Large file keeps growing | base ≥ 1 000 and diff ≥ +50 LOC |
| Package crosses size | head ≥ 30 files or ≥ 3 000 LOC, base below |

Ask: is the growth a new responsibility or more of the same? Only a new responsibility is a finding.
Sketch the split in one sentence.

## Lens C: Dependency direction and cycles

| Signal | Threshold |
| --- | --- |
| First edge between two packages | 0 imports either way on base |
| New 2-cycle | a one-way pair becomes mutual (adding to an already-mutual pair is a note, not a candidate) |
| Stable to volatile edge | from I ≤ 0.30 to I ≥ 0.85, with I = out/(in+out) on base |
| Module enters an import cycle | joins or creates an SCC |
| File coupling | ≥ 8 distinct `infrahub.*` packages imported, base below |

Ask: does the edge contradict the reference frame? Trace one step further: does the target already
import something that imports the source? Name the cycle it is about to close. Without a frame, a
direction finding becomes an open question instead.

## Lens D: Functional sense

Is there a domain reason, stated in the pull request or visible in the code, why feature A now needs
feature B? If the pull request states it, drop the candidate or downgrade it to a note. Would a user
of A be surprised to find B on its path, at startup, in its failure modes, or in its permissions?

## The report

State the reference frame, the commit pair the pass was run on, and the target branch as context
only. The target branch never carries a verdict.

Then at most seven findings, ordered by cost of deferring: the number of sites that have to change
first, then the fan-in of the packages involved. Anything past the cap gets one line.

```markdown
### <n>. <title> (Lens <A|B|C|D>)

- **Evidence:** the compare line, `<file>:<line>` or `<pkg> → <pkg>`, with the number that crossed
- **Future scenario:** <concrete event>
- **Alternative:** <one or two sentences>
- **Cost of deferring:** <sites, packages, migrations, with counts>
- **Hand-off:** none | issue (`creating-issues`) | ADR (`opsmill-dev:creating-adrs`, `dev/adr/`)
```

Close with two sections, one line per entry: **Open questions**, where a direction candidate with no
reference frame lands, and **Positives**, for edges removed and files shrunk. Offer the hand-offs.
Never open an issue or write an ADR without a yes.

An empty findings list is a valid result, as long as the frame is named and the comparison the pass
ran on is shown.

## Anti-patterns

- A crossing with no future scenario is not a finding. Drop it.
- No number in the report that you did not read out of a command's output. Show the command.
- No timing or merge verdict, ever.
- No generic smells (naming, duplication, function length). Other passes own those.
- No direction finding on principles alone. Cite the frame, or ask a question.

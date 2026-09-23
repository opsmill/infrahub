# Structural review

> Part of: `dev/guidelines/reviews/` | Related: [Repository Organization](../repository-organization.md)

A structural pass reads a diff for the risks it adds to the shape of the codebase: a special case
that will be copied, a file that just took on a second job, an import that points the wrong way.
It reports risks and never decides.

## Files

| File | Contents |
| --- | --- |
| [lenses.md](lenses.md) | The four lenses: signals, thresholds, and the question each one asks |
| [reporting.md](reporting.md) | Report structure, ordering, hand-offs, anti-patterns |

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

## A new package in the diff

Apply the four lenses to its internals. Its placement is an open question and an ADR candidate,
not a finding.

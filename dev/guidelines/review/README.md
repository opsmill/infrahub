# Review passes

> Part of: `dev/guidelines/review/` | Related: [Reviewing with cubic](../../guides/reviewing-with-cubic.md), [`cubic.yaml`](../../../cubic.yaml)

Each pass reads the same diff for a different class of risk, one file per pass. A pass reports what
it finds and hands the decision back: none of them gates a merge.

| Pass | Reads | Run by |
| --- | --- | --- |
| [Architectural review](architectural-review.md) | Risks the diff adds to the shape of the codebase: special cases that will be copied, files taking on a second job, imports pointing the wrong way | An agent or a human, on request |
| [Backend conventions](backend.md) | `backend/infrahub/**`, `python_testcontainers/**`, `tasks/**` | cubic |
| [Backend test conventions](testing.md) | `backend/tests/**`, `python_testcontainers/tests/**` | cubic |
| [Frontend conventions](frontend.md) | `frontend/app/**` | cubic |

## The cubic checklists

`.cubic/frontend.md`, `.cubic/backend.md` and `.cubic/testing.md` are symlinks into this directory.
`cubic.yaml` attaches each one to the paths above for pull request reviews, and `CUBIC_CHECKLISTS`
in `tasks/dev.py` mirrors those filters for local reviews. Change a path filter in one and change it
in the other.

Keep each checklist under 9,000 characters: cubic reads only the first 10,000 and drops the rest
without warning.

## Adding a pass

State what the pass reports and what it refuses to do, the signals with a threshold each, and the
shape of its report. Say which passes own the ground it does not cover, so two passes never report
the same finding.

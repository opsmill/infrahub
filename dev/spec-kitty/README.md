# SpecKitty (kitty-spec.*)

SpecKitty extends the existing SpecKit workflow with **work-package-based parallelism**, **git worktree isolation**, **structured review**, and **merge phases**.

## How It Differs from SpecKit

| Aspect | SpecKit (`speckit.*`) | SpecKitty (`kitty-spec.*`) |
|--------|----------------------|---------------------------|
| Task execution | Sequential (tasks.md top-to-bottom) | Parallel via work packages |
| Isolation | Single branch | Git worktrees per WP |
| Review | Manual | Structured quality gates |
| Merge | N/A | Explicit merge phase with conflict detection |
| Dashboard | N/A | Terminal + browser kanban |

## Shared Artifacts

Both tools share two directories at the repository root:

- `.specify/` -- Infrastructure (scripts, templates, constitution)
  - `.specify/scripts/` -- Bash helpers used by both SpecKit and SpecKitty
  - `.specify/templates/` -- Spec, plan, and task templates
  - `.specify/memory/constitution.md` -- Project constitution
- `specs/` -- Feature artifacts (created per feature branch)
  - `specs/<branch>/spec.md` -- Feature specification
  - `specs/<branch>/plan.md` -- Implementation plan
  - `specs/<branch>/tasks.md` -- Task list
  - `specs/<branch>/research.md` -- Research decisions

## SpecKitty-Only Files

All SpecKitty-specific files live under `dev/spec-kitty/`:

```
dev/spec-kitty/
├── work-packages/<branch>/   # WP files (WP01.md, WP02.md, ...)
├── .worktrees/                # Git worktrees (gitignored)
└── kittify/
    ├── scripts/               # Management scripts
    ├── templates/             # WP template
    └── missions.yaml          # Mission config (placeholder)
```

## Workflow

```
/kitty-spec.constitution   (optional) Set project principles
        │
/kitty-spec.specify        Create feature specification
        │
/kitty-spec.research       (optional) Research unknowns
        │
/kitty-spec.plan           Design technical architecture
        │
/kitty-spec.tasks          Generate tasks + work packages
        │
/kitty-spec.implement      Implement WP in isolated worktree
        │                  (repeat for each WP, can run in parallel)
/kitty-spec.review         Review completed WP against quality gates
        │
/kitty-spec.merge          Merge WPs back, clean up worktrees
        │
/kitty-spec.dashboard      View status at any time
```

## Quick Start

```
/kitty-spec.specify Add OAuth2 integration for the API (ifc-2140)
```

This creates the spec, then follow the handoff suggestions through the workflow.

## Work Package Lanes

Each WP moves through these lanes:

- **planned** -- Ready to be implemented
- **doing** -- Currently being worked on (in a worktree)
- **for_review** -- Implementation complete, needs review
- **done** -- Reviewed and approved, ready to merge

## Scripts

```bash
# List WPs and their status
dev/spec-kitty/kittify/scripts/manage-workpackages.sh list <branch>

# View kanban summary
dev/spec-kitty/kittify/scripts/manage-workpackages.sh status <branch>

# Launch browser dashboard
python dev/spec-kitty/kittify/scripts/dashboard.py --feature <branch>
```

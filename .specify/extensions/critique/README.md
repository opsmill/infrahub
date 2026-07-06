# Spec Critique Extension for Spec Kit

Dual-lens critical review of the specification and plan from both product strategy and engineering risk perspectives, before committing to implementation.

## Installation

```bash
specify extension add critique --from https://github.com/arunt14/spec-kit-critique/archive/refs/tags/v1.0.0.zip
```

## Usage

```bash
/speckit.critique.run [focus area]
```

Run after `/speckit.plan` and before `/speckit.tasks` to challenge the plan.

## What It Does

- **Product Lens**: Is this solving the right problem? Scope? User impact? Alternatives?
- **Engineering Lens**: Architecture risks? Security? Scaling? Testing strategy?
- Checks spec/plan against project constitution
- Generates structured critique report with consolidated findings
- Severity levels: 🎯 Must-Address, 💡 Recommendation, 🤔 Question
- Read-only for existing artifacts — proposes changes, doesn't apply them

## Critique Report

Reports are generated at `FEATURE_DIR/critiques/critique-{timestamp}.md` using `commands/critique-template.md`.

## Workflow Position

```
/speckit.plan → /speckit.critique.run → /speckit.tasks
```

## Hook

This extension hooks into `after_plan` — you'll be prompted to run the critique after planning completes.

## License

MIT

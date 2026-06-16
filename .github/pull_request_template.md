<!--
This template is a guide, not a gate. Use as much or as little as helps the
reviewer understand your change. For straightforward PRs (dependency bumps,
linting fixes, CI tweaks, typos) a one-liner description is perfectly fine
-- delete the sections that don't add value.

Rule of thumb: the more the change affects behavior, the more sections you
should fill in.
-->

# Why

<!-- Problem statement: what's broken/slow/confusing/missing today? (1-3 sentences) -->

<!-- Goal: what outcome does this PR achieve? -->

<!-- Non-goals: what this PR intentionally does NOT do (prevents scope creep) -->

Closes <!-- #issue -->

## What changed

<!-- Group changes by intent, not by file. -->

<!-- Behavioral changes: what users/systems will observe differently -->
-

<!-- Implementation notes: key design choices, tradeoffs, notable refactors -->

<!-- What stayed the same: especially useful if you touched sensitive areas -->
<!-- e.g., "No schema changes", "API contract unchanged", "Only affects branch X" -->

<!-- If the diff is large, add a suggested review order:
### Suggested review order
1. Start with ...
2. Then ...
3. Tests are ...
-->

## How to review

<!-- Key files/areas to focus on vs. mechanical/generated changes -->

<!-- Risky or uncertain parts where you want extra scrutiny -->

<!-- Alternatives considered (only if it affects future direction) -->

## How to test

<!-- Make it runnable and specific -->

```bash
# Commands to validate
```

<!-- Expected outputs, screenshots, or links to CI results -->

## Impact & rollout

<!-- Delete items that don't apply -->

- **Backward compatibility:** <!-- any breaking changes or migration steps -->
- **Performance:** <!-- implications, measurements if relevant -->
- **Config/env changes:** <!-- new settings, feature flags, env vars -->
- **Deployment notes:** <!-- "safe to deploy" vs "requires coordinated release" -->

## Checklist

- [ ] Tests added/updated
- [ ] [Changelog entry](../dev/guidelines/changelog.md) added (`uv run towncrier create ...`)
- [ ] External docs updated (if user-facing or ops-facing change)
- [ ] Internal .md docs updated (internal knowledge and AI code tools knowledge)
- [ ] I have reviewed AI generated content

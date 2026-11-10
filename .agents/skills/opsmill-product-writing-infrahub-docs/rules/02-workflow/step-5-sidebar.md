# Step 5 — Update sidebar

Modify `docs/sidebars.ts` so the entries match the structure agreed at the outline gate. Use the small color-matched caret (already styled in `custom.css`) for nested categories where used.

> **Other repos:** substitute the sidebar mechanism resolved in [Step 0.5](step-0.5-detect-repo.md). If the repo has no sidebar file (e.g. README-only or MkDocs with auto-nav), skip this step and note in the PR description.

## Critical: hub categories must have a clickable link

In `sidebars.ts`, every category that becomes a hub must include:

```ts
link: { type: 'doc', id: '<feature>/overview' }
```

Without this, the category caret expands but the label itself is dead — clicking "Profiles" or "Branches" does nothing. The Groups, Profiles, and Branches categories all have this; it's a recurring bug to forget. Verify after writing the sidebar entry.

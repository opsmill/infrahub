# Contract: GET /api/config — New Fields

**User Story**: US1 (Global Configuration), US4 (Manual Delete UI)
**Type**: REST API (read-only, config exposure)
**Change**: Add two new fields to the config response so the frontend can conditionally render the Git deletion checkbox.

---

## Endpoint

```
GET /api/config
```

Authentication: Required (existing behavior unchanged)

## Response Schema (new fields only)

```json
{
  "main": {
    "delete_branch_after_merge": false
  },
  "git": {
    "delete_git_branch_after_merge": false
  }
}
```

Both fields are `boolean`. Default is `false`.

## Frontend Use

The `BranchDeleteButton` reads these values via the existing config query mechanism. The Git deletion checkbox is shown when:

```
branch.sync_with_git === true
AND branch.status === "MERGED"
AND config.git.delete_git_branch_after_merge === false
```

If `config.git.delete_git_branch_after_merge` is already `true`, the checkbox is hidden (deletion will happen automatically; no need to present the option).

## Notes

- No new endpoint; these fields are added to the existing config response
- Regenerate generated types after changing the config response model: `npm run codegen`

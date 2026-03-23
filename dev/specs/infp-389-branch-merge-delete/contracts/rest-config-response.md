# Contract: GET /api/config — New Fields

**User Story**: US1 (Global Configuration), US4 (Manual Delete UI)
**Type**: REST API (read-only, config exposure)
**Change**: Add new fields to the config response so the frontend can conditionally render the Git deletion checkbox.

---

## Endpoint

```
GET /api/config
```

Authentication: Required (existing behavior unchanged)

## Response Schema (new fields)

### Implemented ✅

`main.delete_branch_after_merge` is exposed in the config response:

```json
{
  "main": {
    "delete_branch_after_merge": false
  }
}
```

Field is `boolean`, default `false`. Present in `openapi.json` and `types.generated.ts`.

### Not yet exposed ⬜

`git.delete_git_branch_after_merge` (defined in `GitSettings` in `config.py`) is **not** included in the `GET /api/config` response. The `git` section is not part of the config API response schema. This field is only available server-side.

**Impact on US4 (T014)**: `BranchDeleteButton` cannot read `config.git.delete_git_branch_after_merge` from the REST API as currently designed. Before implementing T014, either:
- Expose `GitSettings` (or just `delete_git_branch_after_merge`) in the config response, or
- Use an alternative approach (e.g., always show the checkbox and let the backend deduplicate)

## Frontend Use (intended, pending T014)

The `BranchDeleteButton` will read `main.delete_branch_after_merge` from the config response. The Git deletion checkbox visibility logic depends on `git.delete_git_branch_after_merge` being exposed first (see above).

## Notes

- No new endpoint; fields are added to the existing config response
- Regenerate generated types after changing the config response model: `npm run codegen`

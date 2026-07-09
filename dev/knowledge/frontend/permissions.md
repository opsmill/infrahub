# Checking permissions on the frontend

There are two kinds of permission, read through different mechanisms. Mixing them up silently denies
access (the gated UI just never appears), so use the right one.

## Object permissions (per-kind)

Read via `useGetObjectPermissions(kind)`; gate with `RequireObjectPermissions`. A permission's
`decision` surfaces as a **string enum name** (`ALLOW`, `ALLOW_DEFAULT`, `ALLOW_OTHER`, `DENY`), and
"granted" means an `ALLOW*` value.

## Global permissions (account-wide, e.g. `manage_global_preferences`)

Read via the generic `InfrahubPermissions` query → `hasGlobalPermission(action)`; gate with
`RequireGlobalPermission action={…}` (the account-wide counterpart of `RequireObjectPermissions`).

**Gotcha — `decision` is a stringified number here, not an enum name.** On `InfrahubPermissions`,
a global permission's `decision` is exposed on a GraphQL `String!` field but carries the backend
`PermissionDecision` **integer** as a string: `"1"`=DENY, `"2"`=ALLOW_DEFAULT, `"4"`=ALLOW_OTHER,
`"6"`=ALLOW_ALL (see [backend/permissions.md](../backend/permissions.md)). So "granted" is
`decision ∈ {"2","4","6"}` — captured as `GRANTING_GLOBAL_DECISIONS` in
`entities/permission/domain/model/permission.ts`. Reusing the object-permission idiom
(`decision.startsWith("ALLOW")`) here **always returns false** and silently hides the gated UI.

**Super admin bypasses every action.** A `super_admin` global grant satisfies *any* action —
`hasGlobalPermission` treats it that way, mirroring the backend
(`has_permission(action) == resolve_global_permission(action) or is_super_admin()`). Gate UI on the
action itself (not on an explicit assignment of it), or a super admin loses access the backend would
actually grant.

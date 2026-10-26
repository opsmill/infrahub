# Round 1 feedback — gathered 2026-10-26 from a pasted *Copy all notes* block

Author: the owner (pasted in session).

```
<!-- design-jam:table-header-compact -->
## design-jam feedback — table-header-compact

### Current knobs (Where it acts · rev 1)
- Screen (`screen`): relationship-tab
- Object (tab) (`object`): device-interfaces
- No create permission (`deny`): false
- Branch card header (`branchHeader`): two-lines
- Field label wrap (`labelWrap`): today

### Where it acts · rev 1 — 1 note, 1 open
http://localhost:8080/_proto/table-header-compact?dj.variant=where-it-acts&dj.rev=1&dj.k.screen=relationship-tab&dj.k.object=device-interfaces&dj.k.deny=0&dj.k.branchHeader=two-lines&dj.k.labelWrap=today

1. **Add Interfaces** — is it easy to add the button in the header like that?
   `div > div:nth-of-type(1) > button:nth-of-type(2)`
```

## Triage

1. **Add Interfaces in the page header: is it easy to build?** — addressed (answered, no prototype change). Yes, it is a small change:
   - The header (`object-details-header.tsx`) already has the object's schema, data and permission, which are the props the existing `RelationshipsButtons` needs. Only the relationship name is missing.
   - The header is rendered by the parent route, so it does not receive the child route's `:relationshipName` param. It can read it with `useMatch` on the relationship tab path, then keep it only if the name is one of the schema's tab relationships (`getRelationshipsVisibleInTab`), so the `tasks`, `repository_objects` and `repository_commits` tabs show no button.
   - The header is used only on the object details page, so the IPAM and repository hosts of the relationship table are not affected; they keep only the Columns control.
   - Risks: the header already holds Refresh, Edit, Schema and Actions, so a long label ("Add Bgp Sessions") crowds it at narrow widths, and the button appears and disappears as the user switches tabs.

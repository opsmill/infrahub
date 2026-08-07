# Plan: Build with AI docs (INFP-678)

## Context

[INFP-678](https://opsmill.atlassian.net/browse/INFP-678) notes a gap: the MCP server and Skills each have full documentation, but on an external site (`docs.infrahub.app/mcp`, `docs.infrahub.app/skills`) disconnected from the main `opsmill/infrahub` docs and from a customer's actual journey. Nothing in `Get started` or in feature pages tells a customer the AI path exists. The one precedent is a single sentence in `docs/docs/menu/overview.mdx:95` linking to the `infrahub-managing-menus` skill.

Three layers: a hub page in `Get started`, per-feature "Build X with AI" spoke pages cross-linked from the hub and from the existing manual page via a callout, and an additive Quickstart note. An `AGENTS.md` template for `opsmill/infrahub-template` is a separate repo and is out of scope here — follow-up task.

Scope for this pass (confirmed with user): hub page, callouts, Quickstart note, and three pilot spoke pages — Schema, Objects, Menus. Querying data (graph traversal) is deferred to a later pass. AI badge component deferred.

## Full candidate catalog

| Domain | Skill(s) | MCP tool(s) | Manual doc home | This pass |
|---|---|---|---|---|
| Schema | `infrahub-managing-schemas` | `get_schema` | `schema/create-and-load.mdx` | Yes |
| Objects / data (YAML) | `infrahub-managing-objects`, `infrahub-importing-data` | `node_upsert`, `get_nodes`, `search_nodes` | `objects/load-from-yaml.mdx` | Yes |
| Menus | `infrahub-managing-menus` | `get_schema` | `menu/overview.mdx` | Yes (upgrades existing one-liner) |
| Querying / analyzing data | `infrahub-analyzing-data` | `query_graphql`, `get_nodes`, `search_nodes`, `find_paths`, `find_reachable` | `graph-traversal/overview.mdx` | Future |
| Generators | `infrahub-managing-generators` | `mutate_graphql` (indirect) | `generators/overview.mdx` | Future |
| Transformations | `infrahub-managing-transforms` | — | `transformations/overview.mdx` | Future |
| Checks & Validation | `infrahub-managing-checks` | — | `checks/overview.mdx` | Future |
| Branches & Proposed Changes | — (MCP-only) | `propose_changes`, `reset_session_branch`, `get_session_info` | `branches/overview.mdx`, `proposed-changes/overview.mdx` | Future |
| Repo / project hygiene | `infrahub-auditing-repo`, `infrahub-reporting-issues`, `infrahub-collecting-diagnostics` | — | Development Resources | Future |

The MCP write model is the same everywhere, so state it once on the hub page rather than per spoke: writes land on an auto-created session branch, never touch the default branch directly, and reach `main` only through `propose_changes` + human review — the same Proposed Change workflow as any manual change.

## Files to Create

### Hub page

| File | Sidebar id / label | Content |
|---|---|---|
| `docs/docs/overview/build-with-ai.mdx` | `overview/build-with-ai`, "Build with AI" | What "building with AI" means (Skills + MCP), install snippets for each with links out to `docs.infrahub.app/skills` and `/mcp`, the shared safety-model paragraph, a "Where to use it" list linking the three spoke pages below, and a link to the Quickstart note |

### Per-feature spoke pages

| File | Sidebar placement | Manual page it pairs with |
|---|---|---|
| `docs/docs/schema/build-with-ai.mdx` | "Schema operations" category, alongside `schema/create-and-load` | `schema/create-and-load.mdx` |
| `docs/docs/objects/build-with-ai.mdx` | `Objects` category, alongside `objects/load-from-yaml` | `objects/load-from-yaml.mdx` |
| `docs/docs/menu/build-with-ai.mdx` | "Display & presentation" category, right after `menu/overview` | `menu/overview.mdx` |

Each spoke page uses minimal front matter (`title: Build <X> with AI`, matching `schema/create-and-load.mdx`'s convention) and the same structure, so the set is a template for future domains:

1. One paragraph: what the manual page covers, and that this is the AI-assisted alternative for the same outcome.
2. "What you get" — bullets naming the exact skill(s)/MCP tool(s) from the catalog above.
3. "Install" — 2-3 line snippet, linking out to `docs.infrahub.app/skills` or `/mcp` for full setup.
4. "Prompt examples" — 2-3 concrete prompts grounded in the real skill/tool names for that domain.
5. "Related" — links back to the manual page and to the Build with AI hub.

## Files to Modify

| File | Change |
|---|---|
| `docs/sidebars.ts` | Insert `overview/build-with-ai` into `Get started`'s `items`, between the `Getting Started` category and `'faq/faq'`. Add the three spoke doc ids to their categories per the placement table above |
| `docs/docs/schema/overview.mdx` | Add a bullet to "In this section" linking the new spoke page |
| `docs/docs/objects/overview.mdx` | Add a bullet to "What you can do with objects" linking the new spoke page |
| `docs/docs/schema/create-and-load.mdx` | Add an `:::info` callout after the existing schema-validation note |
| `docs/docs/objects/load-from-yaml.mdx` | Add an `:::info` callout after the intro paragraph, before "Prerequisites" |
| `docs/docs/menu/overview.mdx` | Replace the line-95 sentence with the same `:::info` callout, now also linking the new dedicated page |
| `docs/docs/overview/quickstart.mdx` | Add one `:::info` callout after the intro/"What you will build" bullets, before "Prerequisites" — no changes to the manual steps, tabs, or verification blocks |

Each callout is one short paragraph: "Prefer to build this with AI? See [Build \<X\> with AI](./build-with-ai.mdx)." Use `:::info` — the documented convention in `docs/docs/development/docs.mdx` for "additional, helpful information that isn't required to complete the task."

## Out of Scope

- AI badge component (`AiBadge.jsx`) — deferred until the page set has grown.
- `AGENTS.md` template for `opsmill/infrahub-template` — separate repo, separate follow-up. Note for later: the template's `README.md` already documents a skill-routing table and `/speckit.*` workflow that belongs in an `AGENTS.md` rather than a README.
- The five "Future" rows in the catalog table — documented roadmap, not built this pass.

## Execution Order

1. Create the three spoke pages.
2. Create the hub page (links to the spokes, so build it after them).
3. Update `docs/sidebars.ts`.
4. Add callouts to the three manual pages and the Quickstart.
5. Add "related links" bullets to `schema/overview.mdx` and `objects/overview.mdx`.

## Verification

```bash
uv run invoke docs.lint
uv run invoke docs.build
uv run invoke docs.serve
```

- `Get started` sidebar shows "Build with AI" between "Getting Started" and "FAQ".
- Each of the three feature sections shows its new spoke page in the right position.
- Each callout renders and links correctly; the Quickstart note appears without disturbing the existing steps.
- No broken links (`docs.build` catches these).

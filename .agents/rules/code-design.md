# Naming, reuse and simplicity

Applies to every source file, Python and TypeScript. The area rules say which layer owns the code; this one says how to name it and whether to write it at all.

## Naming

- Name a file after what it holds and a function after what it does or returns: a verb for an action (`create_branch`, `getBranches`), a noun for a value, `is_`/`has_` for a boolean.
- Use the term the codebase and the Infrahub domain already use (node, peer, branch, schema kind), and one term per concept across the change.
- Do not name a function, class or variable only `data`, `info`, `result`, `manager`, `handle` or `process`; say what it holds or does.
- Do not put the type or the implementation in a name: `nodes`, not `node_list`.
- A rename updates every caller, test name and doc that uses the old name.

## Reuse or duplicate

- Before writing a function, component, query or type, search for one that does the same job. Reuse it when it serves the same need for the same domain reason.
- Write a separate one when the needs differ: other domain rules, another owner, or other reasons to change. Do not merge two such uses behind a flag, a mode parameter or an override that switches behaviour.
- A deliberate copy keeps only what its new use needs.

## Simplicity

- Write the simplest design that meets the requirement: no base class, protocol, factory, registry or generic helper with a single implementation and no second use in the change.
- No parameter, option, setting or fallback that no caller uses, and no function that only forwards its arguments to another.
- Inline a helper used once, unless its name states a domain concept or a test calls it on its own.
- Delete the code, branches and exports the change leaves unused.

## Not violations

- Two similar functions whose domain rules differ.
- A `utils.ts` or `helpers.py` next to the code it serves, holding helpers for that code only.
- An interface module with one implementation that breaks an import cycle.

Full reference: `dev/guidelines/backend/component-design.md`; `dev/guidelines/backend/checklist.md` ("How will naming align with existing code patterns?"); `dev/guidelines/frontend/component-patterns.md` ("Reuse Before Reinvent"); `dev/guidelines/frontend/naming-conventions.md`.

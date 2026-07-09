# Contract: Tier-1 Biome Guard

The Tier-1 guard is a Biome `overrides` entry using `noRestrictedImports`, scoped to
already-migrated entities' `domain/` folders. It grows one glob per PR.

## Shape (illustrative — confirm exact rule group/keys against `@biomejs/biome@2.4.16`)

```jsonc
// biome.jsonc — overrides[]
{
  "includes": [
    "src/entities/role-manager/domain/**",
    "src/entities/branches/domain/**"
    // ← one line appended per migrated entity
  ],
  "linter": {
    "rules": {
      "nursery": {
        "noRestrictedImports": {
          "level": "error",
          "options": {
            "patterns": [
              { "regex": ".*/graphql/generated(/.*)?$" },
              { "regex": ".*/api/rest/types\\.generated$" }
            ],
            "paths": {
              "@apollo/client": "domain/ must not import Apollo — belongs in api/ or ui/",
              "@tanstack/react-query": "domain/ must not import TanStack — belongs in ui/",
              "react": "domain/ must be framework-free"
              // + storage and toast library entries
            }
          }
        }
      }
    }
  }
}
```

## Contract requirements

1. The override's `includes` list contains a `domain/**` glob for **every migrated entity and no
   unmigrated entity** at all times (so the rule only ever passes).
2. The forbidden set covers, at minimum: `@apollo/client`, `@tanstack/react-query`, `react`,
   `**/graphql/generated`, `shared/api/rest/types.generated`, browser storage, notification/toast libs.
3. Each migration PR appends exactly its own entity's `domain/**` glob (one line) — reviewable as part
   of that PR's diff.
4. `pnpm biome` MUST pass on the PR branch before merge.

## Acceptance test per PR

- Add the entity's `domain/**` glob to `includes`.
- Run `pnpm biome`; it MUST pass (proves the migrated `domain/` is clean of forbidden imports).
- Temporarily re-add a forbidden import in a migrated `domain/` file and confirm `pnpm biome` **fails**
  (proves the guard is live, not inert) — then revert. Do this once, on the `role-manager` PR, to
  validate the config end-to-end.

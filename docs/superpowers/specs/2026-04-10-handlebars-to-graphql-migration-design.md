# Migrate Handlebars GraphQL Templates to gql.tada / jsonToGraphQLQuery

## Summary

Replace all 9 Handlebars-based GraphQL query templates in the frontend with either gql.tada (static queries) or jsonToGraphQLQuery (dynamic queries). Rename queries for clarity in logs and debugging. Remove the Handlebars dependency entirely.

## Motivation

- Handlebars templates have no type safety and interpolate values directly into query strings
- The codebase already uses gql.tada and jsonToGraphQLQuery extensively — Handlebars is the odd one out
- Query naming is inconsistent across the three approaches

## Classification

Each Handlebars file was analyzed by reading its call sites to determine whether the query shape is truly dynamic at runtime.

### Static (migrate to gql.tada) — 6 files

These queries have constant root fields at their call sites. Template parameters like `kind` resolve to constants, and interpolated values like `id` become proper GraphQL `$variables`.

| File | Root field | Constant source |
|------|-----------|-----------------|
| `entities/tasks/api/getTasksItemDetailsTitle.ts` | `InfrahubTask` | `TASK_OBJECT` |
| `entities/proposed-changes/api/getProposedChangesArtifactsThreads.ts` | `CoreArtifactThread` | `PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT` |
| `entities/proposed-changes/api/getProposedChangesFilesThreads.ts` | `CoreFileThread` | `PROPOSED_CHANGES_FILE_THREAD_OBJECT` |
| `entities/proposed-changes/api/getProposedChangesObjectThreadComments.ts` | `CoreObjectThread` | `PROPOSED_CHANGES_OBJECT_THREAD_OBJECT` |
| `entities/proposed-changes/api/getProposedChangesObjectThreads.ts` | `CoreObjectThread` | `PROPOSED_CHANGES_OBJECT_THREAD_OBJECT` |
| `entities/diff/api/getValidatorDetails.ts` | `CoreValidator` | Hardcoded in template |

Notes:
- `getProposedChangesArtifactsThreads` and `getProposedChangesFilesThreads` have `{{#each attributes}}` blocks that receive no data at their call sites — dead code, removed during migration.
- `getValidatorDetails` has `checks {{#if filters}}({{{filters}}}){{/if}}` where filters is a raw string of `offset: X, limit: Y` — converted to proper `$checksOffset: Int, $checksLimit: Int` variables.

### Dynamic (migrate to jsonToGraphQLQuery) — 3 files

These queries have root fields or argument names that vary at runtime based on schema introspection.

| File | Why dynamic |
|------|------------|
| `entities/nodes/api/getObjectDisplayLabel.ts` | `kind` from component prop (any schema type) |
| `entities/nodes/api/getRelationshipParent.ts` | `kind` + `attribute` name both runtime-dependent |
| `entities/groups/api/get-groups-from-api.ts` | `objectKind` from caller params |

## Naming Convention

### Static queries (gql.tada)

Operation name = TypeScript constant name. `UPPER_SNAKE_CASE`.

| Old export name | New export & operation name |
|----------------|---------------------------|
| `getTaskItemDetailsTitle` | `GET_TASK_DETAILS_TITLE` |
| `getProposedChangesArtifactsThreads` | `GET_ARTIFACT_THREADS` |
| `getProposedChangesFilesThreads` | `GET_FILE_THREADS` |
| `getProposedChangesObjectThreadComments` | `GET_OBJECT_THREAD_COMMENTS` |
| `getProposedChangesObjectThreads` | `GET_OBJECT_THREADS` |
| `getValidatorDetails` | `GET_VALIDATOR_DETAILS` |

### Dynamic queries (jsonToGraphQLQuery)

Operation name uses `__name`: `functionName__${differentiator}` (PascalCase function name, double underscore separator).

| Function name | `__name` |
|--------------|----------|
| `getObjectDisplayLabel({ kind })` | `getObjectDisplayLabel__${kind}` |
| `getRelationshipParent({ kind })` | `getRelationshipParent__${kind}` |
| `getObjectGroups({ objectKind })` | `getObjectGroups__${objectKind}` |

Note: `getGroupsQuery` renamed to `getObjectGroups` for clarity.

## Detailed Changes

### Static query: `getTasksItemDetailsTitle.ts`

**Before:**
```typescript
import Handlebars from "@/shared/libs/handlebars";

export const getTaskItemDetailsTitle = Handlebars.compile(`
query GetTaskDetails {
  {{kind}}(ids: ["{{id}}"]) {
    count
    edges {
      node {
        title
      }
    }
  }
}
`);
```

**After:**
```typescript
import { graphql } from "gql.tada";

export const GET_TASK_DETAILS_TITLE = graphql(`
  query GET_TASK_DETAILS_TITLE($ids: [ID]) {
    InfrahubTask(ids: $ids) {
      count
      edges {
        node {
          title
        }
      }
    }
  }
`);
```

**Call site (`pages/tasks/task-details.tsx`) before:**
```typescript
const query = gql(getTaskItemDetailsTitle({ kind: TASK_OBJECT, id: taskId }));
const { loading, error, data, refetch } = useQuery(query);
```

**Call site after:**
```typescript
const { loading, error, data, refetch } = useQuery(GET_TASK_DETAILS_TITLE, {
  variables: { ids: [taskId] },
});
```

### Static query: `getProposedChangesArtifactsThreads.ts`

**After:**
```typescript
import { graphql } from "gql.tada";

export const GET_ARTIFACT_THREADS = graphql(`
  query GET_ARTIFACT_THREADS($changeIds: String) {
    CoreArtifactThread(change__ids: $changeIds) {
      count
      edges {
        node {
          id
          display_label
          __typename
          line_number { value }
          storage_id { value }
          resolved { value }
          comments {
            edges {
              node_metadata {
                created_at
                created_by { display_label }
              }
              node {
                id
                text { value }
              }
            }
          }
        }
      }
    }
  }
`);
```

**Call site (`artifact-content-diff.tsx`):** Drops `schemaList.find()` lookup for kind, passes `changeIds` as variable. The `skip` condition simplifies to `!proposedChangeId`.

### Static query: `getProposedChangesFilesThreads.ts`

**After:**
```typescript
import { graphql } from "gql.tada";

export const GET_FILE_THREADS = graphql(`
  query GET_FILE_THREADS($changeIds: String) {
    CoreFileThread(change__ids: $changeIds) {
      count
      edges {
        node {
          id
          display_label
          resolved { value }
          __typename
          file { value }
          commit { value }
          repository {
            node { id }
          }
          line_number { value }
          comments {
            edges {
              node_metadata {
                created_at
                created_by { display_label }
              }
              node {
                id
                text { value }
              }
            }
          }
        }
      }
    }
  }
`);
```

**Call site (`file-content-diff.tsx`):** Same simplification as artifact threads.

### Static query: `getProposedChangesObjectThreadComments.ts`

**After:**
```typescript
import { graphql } from "gql.tada";

export const GET_OBJECT_THREAD_COMMENTS = graphql(`
  query GET_OBJECT_THREAD_COMMENTS($changeIds: String, $objectPath: String) {
    CoreObjectThread(change__ids: $changeIds, object_path__value: $objectPath) {
      count
      edges {
        node {
          __typename
          id
          display_label
          resolved { value }
          comments {
            count
            edges {
              node_metadata {
                created_at
                created_by { display_label }
              }
              node {
                id
                display_label
                text { value }
              }
            }
          }
        }
      }
    }
  }
`);
```

**Call site (`comments.tsx`):** Drops `schemaList.find()`, drops `"query { ok }"` fallback, uses `skip: !proposedChangeId`.

### Static query: `getProposedChangesObjectThreads.ts`

**After:**
```typescript
import { graphql } from "gql.tada";

export const GET_OBJECT_THREADS = graphql(`
  query GET_OBJECT_THREADS($changeIds: String, $objectPath: String) {
    CoreObjectThread(change__ids: $changeIds, object_path__value: $objectPath) {
      count
      edges {
        node {
          __typename
          id
          comments { count }
        }
      }
      permissions {
        edges {
          node {
            kind
            view
            create
            update
            delete
          }
        }
      }
    }
  }
`);
```

**Call site (`thread.tsx`):** Same simplification pattern.

### Static query: `getValidatorDetails.ts`

**After:**
```typescript
import { graphql } from "gql.tada";

export const GET_VALIDATOR_DETAILS = graphql(`
  query GET_VALIDATOR_DETAILS($ids: [ID], $checksOffset: Int, $checksLimit: Int) {
    CoreValidator(ids: $ids) {
      edges {
        node {
          id
          display_label
          conclusion { value }
          started_at { value }
          completed_at { value }
          state { value }
          ... on CoreRepositoryValidator {
            repository {
              node { display_label }
            }
          }
          ... on CoreArtifactValidator {
            definition {
              node {
                display_label
                name { value }
                description { value }
              }
            }
          }
          checks(offset: $checksOffset, limit: $checksLimit) {
            count
            edges {
              node {
                id
                display_label
                name { value }
                message { value }
                severity { value }
                conclusion { value }
                kind { value }
                origin { value }
                created_at { value }
                ... on CoreDataCheck {
                  conflicts { value }
                }
                ... on CoreSchemaCheck {
                  conflicts { value }
                }
                ... on CoreFileCheck {
                  files { value }
                  commit { value }
                }
                ... on CoreArtifactCheck {
                  storage_id { value }
                  artifact_id { value }
                }
                __typename
              }
            }
          }
        }
      }
    }
  }
`);
```

**Call site (`validator-details.tsx`):** Drops raw filter string construction, passes `checksOffset` and `checksLimit` as variables.

### Dynamic query: `getObjectDisplayLabel.ts`

**After:**
```typescript
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

export const getObjectDisplayLabel = ({
  kind,
  peerField,
}: {
  kind: string;
  peerField?: string;
}) => {
  return jsonToGraphQLQuery({
    query: {
      __name: `getObjectDisplayLabel__${kind}`,
      __variables: { ids: "[ID]" },
      [kind]: {
        __args: { ids: new VariableType("ids") },
        edges: {
          node: {
            id: true,
            display_label: true,
            ...(peerField ? { [peerField]: { value: true } } : {}),
          },
        },
      },
    },
  });
};
```

**Call site (`id.tsx`):** Minimal change — wraps with `gql()` instead of `graphql()`.

### Dynamic query: `getRelationshipParent.ts`

**After:**
```typescript
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

export const getRelationshipParent = ({
  kind,
  attribute,
}: {
  kind: string;
  attribute: string;
}) => {
  return jsonToGraphQLQuery({
    query: {
      __name: `getRelationshipParent__${kind}`,
      __variables: { ids: "[ID]" },
      [kind]: {
        __args: { [attribute]: new VariableType("ids") },
        count: true,
        edges: {
          node: {
            id: true,
            display_label: true,
          },
        },
      },
    },
  });
};
```

**Call site (`get-default-parent-from-api.ts`):** Stops passing `id` into the builder. Passes `variables: { ids: [id] }` to `graphqlClient.query()`.

### Dynamic query: `get-groups-from-api.ts`

Rename internal `getGroupsQuery` to `getObjectGroups`.

**After:**
```typescript
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

const getObjectGroups = ({ objectKind }: { objectKind: string }) => {
  return jsonToGraphQLQuery({
    query: {
      __name: `getObjectGroups__${objectKind}`,
      __variables: { ids: "[ID]" },
      [objectKind]: {
        __args: { ids: new VariableType("ids") },
        edges: {
          node: {
            member_of_groups: {
              count: true,
              edges: {
                node: {
                  id: true,
                  display_label: true,
                  description: { value: true },
                  group_type: { value: true },
                  members: { count: true },
                },
              },
            },
          },
        },
        permissions: {
          edges: {
            node: {
              kind: true,
              view: true,
              create: true,
              update: true,
              delete: true,
            },
          },
        },
      },
    },
  });
};
```

**Call site:** Passes `variables: { ids: [objectId] }` to `graphqlClient.query()`.

### Cleanup

- Delete `src/shared/libs/handlebars.ts`
- Remove `handlebars` from `package.json` dependencies
- Run `pnpm install` to update lockfile

### Call site simplification (proposed-changes queries)

The 4 proposed-changes call sites currently do:
```typescript
const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_*_OBJECT);
const queryString = schemaData ? handlebarsTemplate({ kind: schemaData.kind, ... }) : "query { ok }";
const query = gql(queryString);
useQuery(query, { skip: !schemaData });
```

After migration this simplifies to:
```typescript
useQuery(GET_*_THREADS, {
  variables: { changeIds: proposedChangeId, ... },
  skip: !proposedChangeId,
});
```

The `schemaList.find()` lookup and `"query { ok }"` fallback are eliminated.

## Out of Scope

- Renaming existing gql.tada or jsonToGraphQLQuery queries elsewhere in the codebase
- Migrating any other query patterns
- Changing the GraphQL client (Apollo) or custom hooks

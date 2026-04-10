# Handlebars to gql.tada / jsonToGraphQLQuery Migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all 9 Handlebars-based GraphQL query templates with gql.tada (6 static) or jsonToGraphQLQuery (3 dynamic), rename queries for debugging clarity, and remove the Handlebars dependency.

**Architecture:** In-place migration of each file. Static queries become typed gql.tada document nodes with proper `$variables`. Dynamic queries become jsonToGraphQLQuery builder functions using `VariableType` for parameterization. Call sites are updated to pass variables through Apollo instead of string interpolation.

**Tech Stack:** gql.tada, json-to-graphql-query, Apollo Client, TypeScript

**Spec:** `docs/superpowers/specs/2026-04-10-handlebars-to-graphql-migration-design.md`

---

## Task 1: Migrate `getTasksItemDetailsTitle` to gql.tada

**Files:**
- Modify: `src/entities/tasks/api/getTasksItemDetailsTitle.ts`
- Modify: `src/pages/tasks/task-details.tsx`

- [ ] **Step 1: Rewrite `getTasksItemDetailsTitle.ts`**

Replace the entire file content with:

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

- [ ] **Step 2: Update call site in `task-details.tsx`**

Replace the imports:
```typescript
// Remove these:
import { gql } from "@apollo/client";
import { TASK_OBJECT } from "@/shared/config/constants";
import { getTaskItemDetailsTitle } from "@/entities/tasks/api/getTasksItemDetailsTitle";

// Add this:
import { GET_TASK_DETAILS_TITLE } from "@/entities/tasks/api/getTasksItemDetailsTitle";
```

Replace the query construction:
```typescript
// Before:
const query = gql(
  getTaskItemDetailsTitle({
    kind: TASK_OBJECT,
    id: taskId,
  })
);
const { loading, error, data, refetch } = useQuery(query);

// After:
const { loading, error, data, refetch } = useQuery(GET_TASK_DETAILS_TITLE, {
  variables: { ids: [taskId] },
});
```

Update data access — `TASK_OBJECT` is `"InfrahubTask"`, which matches the query root field, so keep:
```typescript
const taskData = data?.InfrahubTask?.edges?.[0]?.node;
```

Note: `TASK_OBJECT` import was also used for data access. Since the constant is `"InfrahubTask"` and that's now the literal query field, either keep importing the constant for data access or use the string directly. The constant `TASK_OBJECT` is still needed here. Re-add it if the data access line uses it:
```typescript
import { TASK_OBJECT } from "@/shared/config/constants";
```

- [ ] **Step 3: Verify build**

Run: `cd frontend/app && pnpm build`
Expected: No type errors related to `getTasksItemDetailsTitle` or `task-details.tsx`.

- [ ] **Step 4: Commit**

```bash
git add src/entities/tasks/api/getTasksItemDetailsTitle.ts src/pages/tasks/task-details.tsx
git commit -m "refactor: migrate getTasksItemDetailsTitle from Handlebars to gql.tada"
```

---

## Task 2: Migrate `getProposedChangesArtifactsThreads` to gql.tada

**Files:**
- Modify: `src/entities/proposed-changes/api/getProposedChangesArtifactsThreads.ts`
- Modify: `src/entities/diff/ui/artifact-diff/artifact-content-diff.tsx`

- [ ] **Step 1: Rewrite `getProposedChangesArtifactsThreads.ts`**

Replace the entire file content with:

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
          line_number {
            value
          }
          storage_id {
            value
          }
          resolved {
            value
          }
          comments {
            edges {
              node_metadata {
                created_at
                created_by {
                  display_label
                }
              }
              node {
                id
                text {
                  value
                }
              }
            }
          }
        }
      }
    }
  }
`);
```

- [ ] **Step 2: Update call site in `artifact-content-diff.tsx`**

Replace imports:
```typescript
// Remove these:
import { gql, useQuery } from "@apollo/client";
import {
  PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT,
  PROPOSED_CHANGES_FILE_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "@/shared/config/constants";
import { getProposedChangesArtifactsThreads } from "@/entities/proposed-changes/api/getProposedChangesArtifactsThreads";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

// Add these:
import { useQuery } from "@apollo/client";
import {
  PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT,
  PROPOSED_CHANGES_FILE_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "@/shared/config/constants";
import { GET_ARTIFACT_THREADS } from "@/entities/proposed-changes/api/getProposedChangesArtifactsThreads";
```

Remove the `useAtom` import and `nodeSchemasAtom` usage:
```typescript
// Remove:
import { useAtom } from "jotai";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

// Remove from component body:
const [schemaList] = useAtom(nodeSchemasAtom);
const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT);
const queryString = getProposedChangesArtifactsThreads({
  id: proposedChangeId,
  kind: schemaData?.kind,
});
const { loading, error, data, refetch } = useQuery(gql(queryString), {
  skip: !schemaData || !proposedChangeId,
});
```

Replace with:
```typescript
const { loading, error, data, refetch } = useQuery(GET_ARTIFACT_THREADS, {
  variables: { changeIds: proposedChangeId },
  skip: !proposedChangeId,
});
```

Update data access — the old code uses `data[schemaData?.kind]` where `schemaData?.kind` is `"CoreArtifactThread"`:
```typescript
// Before:
const threads =
  data && schemaData?.kind ? data[schemaData?.kind]?.edges?.map((edge: any) => edge.node) : [];

// After:
const threads = data?.CoreArtifactThread?.edges?.map((edge: any) => edge.node) ?? [];
```

Note: `PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT` (`"CoreArtifactThread"`) is still needed for `createObject.mutateAsync({ objectKind: PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT, ... })` calls. Keep that import. `PROPOSED_CHANGES_FILE_THREAD_OBJECT` is used in the `onError` handler for `deleteObject`. Keep that too.

- [ ] **Step 3: Verify build**

Run: `cd frontend/app && pnpm build`
Expected: No type errors related to these files.

- [ ] **Step 4: Commit**

```bash
git add src/entities/proposed-changes/api/getProposedChangesArtifactsThreads.ts src/entities/diff/ui/artifact-diff/artifact-content-diff.tsx
git commit -m "refactor: migrate getProposedChangesArtifactsThreads from Handlebars to gql.tada"
```

---

## Task 3: Migrate `getProposedChangesFilesThreads` to gql.tada

**Files:**
- Modify: `src/entities/proposed-changes/api/getProposedChangesFilesThreads.ts`
- Modify: `src/entities/diff/ui/file-diff/file-content-diff.tsx`

- [ ] **Step 1: Rewrite `getProposedChangesFilesThreads.ts`**

Replace the entire file content with:

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
          resolved {
            value
          }
          __typename
          file {
            value
          }
          commit {
            value
          }
          repository {
            node {
              id
            }
          }
          line_number {
            value
          }
          comments {
            edges {
              node_metadata {
                created_at
                created_by {
                  display_label
                }
              }
              node {
                id
                text {
                  value
                }
              }
            }
          }
        }
      }
    }
  }
`);
```

- [ ] **Step 2: Update call site in `file-content-diff.tsx`**

Replace imports:
```typescript
// Remove these:
import { gql, useQuery } from "@apollo/client";
import { useAtom } from "jotai";
import { getProposedChangesFilesThreads } from "@/entities/proposed-changes/api/getProposedChangesFilesThreads";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

// Add these:
import { useQuery } from "@apollo/client";
import { GET_FILE_THREADS } from "@/entities/proposed-changes/api/getProposedChangesFilesThreads";
```

Remove from component body:
```typescript
// Remove:
const [schemaList] = useAtom(nodeSchemasAtom);
const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_FILE_THREAD_OBJECT);
const queryString =
  schemaData && proposedChangeId
    ? getProposedChangesFilesThreads({
        id: proposedChangeId,
        kind: schemaData.kind,
      })
    : "";
const query = queryString
  ? gql`
      ${queryString}
    `
  : "";
const { loading, error, data, refetch } = query
  ? useQuery(query, { skip: !schemaData })
  : { loading: false, error: null, data: null, refetch: null };
```

Replace with:
```typescript
const { loading, error, data, refetch } = useQuery(GET_FILE_THREADS, {
  variables: { changeIds: proposedChangeId },
  skip: !proposedChangeId,
});
```

Update data access:
```typescript
// Before:
const threads =
  data && schemaData?.kind ? data[schemaData?.kind]?.edges?.map((edge: any) => edge.node) : [];

// After:
const threads = data?.CoreFileThread?.edges?.map((edge: any) => edge.node) ?? [];
```

- [ ] **Step 3: Verify build**

Run: `cd frontend/app && pnpm build`
Expected: No type errors related to these files.

- [ ] **Step 4: Commit**

```bash
git add src/entities/proposed-changes/api/getProposedChangesFilesThreads.ts src/entities/diff/ui/file-diff/file-content-diff.tsx
git commit -m "refactor: migrate getProposedChangesFilesThreads from Handlebars to gql.tada"
```

---

## Task 4: Migrate `getProposedChangesObjectThreadComments` to gql.tada

**Files:**
- Modify: `src/entities/proposed-changes/api/getProposedChangesObjectThreadComments.ts`
- Modify: `src/entities/diff/ui/node-diff/comments.tsx`

- [ ] **Step 1: Rewrite `getProposedChangesObjectThreadComments.ts`**

Replace the entire file content with:

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
          resolved {
            value
          }
          comments {
            count
            edges {
              node_metadata {
                created_at
                created_by {
                  display_label
                }
              }
              node {
                id
                display_label
                text {
                  value
                }
              }
            }
          }
        }
      }
    }
  }
`);
```

- [ ] **Step 2: Update call site in `comments.tsx`**

Replace imports:
```typescript
// Remove these:
import { gql, useQuery } from "@apollo/client";
import { useAtom } from "jotai";
import { getProposedChangesObjectThreadComments } from "@/entities/proposed-changes/api/getProposedChangesObjectThreadComments";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

// Add these:
import { useQuery } from "@apollo/client";
import { GET_OBJECT_THREAD_COMMENTS } from "@/entities/proposed-changes/api/getProposedChangesObjectThreadComments";
```

Remove from component body:
```typescript
// Remove:
const [schemaList] = useAtom(nodeSchemasAtom);
const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT_THREAD_OBJECT);
const queryString = schemaData
  ? getProposedChangesObjectThreadComments({
      id: proposedChangeId,
      path,
      kind: schemaData.kind,
    })
  : "query { ok }";
const query = gql`
  ${queryString}
`;
const { loading, error, data, refetch } = useQuery(query, { skip: !schemaData });
```

Replace with:
```typescript
const { loading, error, data, refetch } = useQuery(GET_OBJECT_THREAD_COMMENTS, {
  variables: { changeIds: proposedChangeId, objectPath: path },
  skip: !proposedChangeId,
});
```

Update data access:
```typescript
// Before:
const thread = data ? data[PROPOSED_CHANGES_OBJECT_THREAD_OBJECT]?.edges[0]?.node : {};

// After:
const thread = data?.CoreObjectThread?.edges?.[0]?.node ?? {};
```

Note: `PROPOSED_CHANGES_OBJECT_THREAD_OBJECT` is still used for `createObject.mutateAsync` and `deleteObject.mutateAsync` calls. Keep that import. Remove `PROPOSED_CHANGES_THREAD_COMMENT_OBJECT` only if it's unused after the change — check that it's still used for `createObject.mutateAsync({ objectKind: PROPOSED_CHANGES_THREAD_COMMENT_OBJECT, ... })`. It is, so keep it.

- [ ] **Step 3: Verify build**

Run: `cd frontend/app && pnpm build`
Expected: No type errors related to these files.

- [ ] **Step 4: Commit**

```bash
git add src/entities/proposed-changes/api/getProposedChangesObjectThreadComments.ts src/entities/diff/ui/node-diff/comments.tsx
git commit -m "refactor: migrate getProposedChangesObjectThreadComments from Handlebars to gql.tada"
```

---

## Task 5: Migrate `getProposedChangesObjectThreads` to gql.tada

**Files:**
- Modify: `src/entities/proposed-changes/api/getProposedChangesObjectThreads.ts`
- Modify: `src/entities/diff/ui/node-diff/thread.tsx`

- [ ] **Step 1: Rewrite `getProposedChangesObjectThreads.ts`**

Replace the entire file content with:

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
          comments {
            count
          }
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

- [ ] **Step 2: Update call site in `thread.tsx`**

Replace imports:
```typescript
// Remove these:
import { gql, useQuery } from "@apollo/client";
import { useAtom } from "jotai";
import { PROPOSED_CHANGES_OBJECT_THREAD_OBJECT } from "@/shared/config/constants";
import { getProposedChangesObjectThreads } from "@/entities/proposed-changes/api/getProposedChangesObjectThreads";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

// Add these:
import { useQuery } from "@apollo/client";
import { GET_OBJECT_THREADS } from "@/entities/proposed-changes/api/getProposedChangesObjectThreads";
```

Remove from component body:
```typescript
// Remove:
const [schemaList] = useAtom(nodeSchemasAtom);
const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT_THREAD_OBJECT);
const queryString = schemaData
  ? getProposedChangesObjectThreads({
      id: proposedChangeId,
      path,
      kind: schemaData.kind,
    })
  : "query { ok }";
const query = gql`
  ${queryString}
`;
const { loading, error, data, refetch } = useQuery(query, { skip: !schemaData });
```

Replace with:
```typescript
const { loading, error, data, refetch } = useQuery(GET_OBJECT_THREADS, {
  variables: { changeIds: proposedChangeId, objectPath: path },
  skip: !proposedChangeId,
});
```

Update data access:
```typescript
// Before:
const thread = data ? data[schemaData.kind]?.edges[0]?.node : {};
const permission = data && getPermission(data?.[schemaData.kind]?.permissions?.edges);

// After:
const thread = data?.CoreObjectThread?.edges?.[0]?.node ?? {};
const permission = data && getPermission(data?.CoreObjectThread?.permissions?.edges);
```

- [ ] **Step 3: Verify build**

Run: `cd frontend/app && pnpm build`
Expected: No type errors related to these files.

- [ ] **Step 4: Commit**

```bash
git add src/entities/proposed-changes/api/getProposedChangesObjectThreads.ts src/entities/diff/ui/node-diff/thread.tsx
git commit -m "refactor: migrate getProposedChangesObjectThreads from Handlebars to gql.tada"
```

---

## Task 6: Migrate `getValidatorDetails` to gql.tada

**Files:**
- Modify: `src/entities/diff/api/getValidatorDetails.ts`
- Modify: `src/entities/diff/ui/checks/validator-details.tsx`

- [ ] **Step 1: Rewrite `getValidatorDetails.ts`**

Replace the entire file content with:

```typescript
import { graphql } from "gql.tada";

export const GET_VALIDATOR_DETAILS = graphql(`
  query GET_VALIDATOR_DETAILS($ids: [ID], $checksOffset: Int, $checksLimit: Int) {
    CoreValidator(ids: $ids) {
      edges {
        node {
          id
          display_label
          conclusion {
            value
          }
          started_at {
            value
          }
          completed_at {
            value
          }
          state {
            value
          }
          ... on CoreRepositoryValidator {
            repository {
              node {
                display_label
              }
            }
          }
          ... on CoreArtifactValidator {
            definition {
              node {
                display_label
                name {
                  value
                }
                description {
                  value
                }
              }
            }
          }
          checks(offset: $checksOffset, limit: $checksLimit) {
            count
            edges {
              node {
                id
                display_label
                name {
                  value
                }
                message {
                  value
                }
                severity {
                  value
                }
                conclusion {
                  value
                }
                kind {
                  value
                }
                origin {
                  value
                }
                created_at {
                  value
                }
                ... on CoreDataCheck {
                  conflicts {
                    value
                  }
                }
                ... on CoreSchemaCheck {
                  conflicts {
                    value
                  }
                }
                ... on CoreFileCheck {
                  files {
                    value
                  }
                  commit {
                    value
                  }
                }
                ... on CoreArtifactCheck {
                  storage_id {
                    value
                  }
                  artifact_id {
                    value
                  }
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

- [ ] **Step 2: Update call site in `validator-details.tsx`**

Replace imports:
```typescript
// Remove these:
import { gql } from "@apollo/client";
import { getValidatorDetails } from "@/entities/diff/api/getValidatorDetails";

// Add this:
import { GET_VALIDATOR_DETAILS } from "@/entities/diff/api/getValidatorDetails";
```

Remove the filter string construction and replace query usage:
```typescript
// Remove:
const filtersString = [
  ...[
    { name: "offset", value: pagination?.offset },
    { name: "limit", value: pagination?.limit },
  ].map((row: any) => `${row.name}: ${row.value}`),
].join(",");

const queryString = getValidatorDetails({
  id,
  filters: filtersString,
});

const query = gql`
  ${queryString}
`;

const { loading, error, data } = useQuery(query);

// Replace with:
const { loading, error, data } = useQuery(GET_VALIDATOR_DETAILS, {
  variables: {
    ids: [id],
    checksOffset: pagination?.offset,
    checksLimit: pagination?.limit,
  },
});
```

- [ ] **Step 3: Verify build**

Run: `cd frontend/app && pnpm build`
Expected: No type errors related to these files.

- [ ] **Step 4: Commit**

```bash
git add src/entities/diff/api/getValidatorDetails.ts src/entities/diff/ui/checks/validator-details.tsx
git commit -m "refactor: migrate getValidatorDetails from Handlebars to gql.tada"
```

---

## Task 7: Migrate `getObjectDisplayLabel` to jsonToGraphQLQuery

**Files:**
- Modify: `src/entities/nodes/api/getObjectDisplayLabel.ts`
- Modify: `src/shared/components/ui/id.tsx`

- [ ] **Step 1: Rewrite `getObjectDisplayLabel.ts`**

Replace the entire file content with:

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

- [ ] **Step 2: Update call site in `id.tsx`**

Replace imports:
```typescript
// Remove:
import { graphql } from "gql.tada";

// Add:
import { gql } from "@apollo/client";
```

Update the query call:
```typescript
// Before:
const { loading, error, data } = useQuery(graphql(getObjectDisplayLabel({ kind })), {
  variables: { ids: [id] },
  context: { uri: CONFIG.GRAPHQL_URL(branch, date) },
});

// After:
const { loading, error, data } = useQuery(gql(getObjectDisplayLabel({ kind })), {
  variables: { ids: [id] },
  context: { uri: CONFIG.GRAPHQL_URL(branch, date) },
});
```

Note: The call site already uses proper `variables: { ids: [id] }` — no change needed there. Only the wrapping function changes from `graphql()` (gql.tada) to `gql()` (Apollo) since the string is now from jsonToGraphQLQuery, not a static template.

- [ ] **Step 3: Verify build**

Run: `cd frontend/app && pnpm build`
Expected: No type errors related to these files.

- [ ] **Step 4: Commit**

```bash
git add src/entities/nodes/api/getObjectDisplayLabel.ts src/shared/components/ui/id.tsx
git commit -m "refactor: migrate getObjectDisplayLabel from Handlebars to jsonToGraphQLQuery"
```

---

## Task 8: Migrate `getRelationshipParent` to jsonToGraphQLQuery

**Files:**
- Modify: `src/entities/nodes/api/getRelationshipParent.ts`
- Modify: `src/entities/nodes/relationships/api/get-default-parent-from-api.ts`

- [ ] **Step 1: Rewrite `getRelationshipParent.ts`**

Replace the entire file content with:

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

- [ ] **Step 2: Update call site in `get-default-parent-from-api.ts`**

The call site currently passes `id` into the template string. Change it to pass `id` as a GraphQL variable:

```typescript
// Before:
const query = gql(
  getRelationshipParent({
    kind: parentRelationship?.peer,
    attribute: `${parentRelationshipAttribute?.name}__ids`,
    id,
  })
);

return graphqlClient.query({
  query,
  context: {
    branch: branchName,
    date: atDate,
    queryDeduplication: false,
    processErrorMessage: () => {},
  },
});

// After:
const query = gql(
  getRelationshipParent({
    kind: parentRelationship?.peer,
    attribute: `${parentRelationshipAttribute?.name}__ids`,
  })
);

return graphqlClient.query({
  query,
  variables: { ids: id ? [id] : undefined },
  context: {
    branch: branchName,
    date: atDate,
    queryDeduplication: false,
    processErrorMessage: () => {},
  },
});
```

- [ ] **Step 3: Verify build**

Run: `cd frontend/app && pnpm build`
Expected: No type errors related to these files.

- [ ] **Step 4: Commit**

```bash
git add src/entities/nodes/api/getRelationshipParent.ts src/entities/nodes/relationships/api/get-default-parent-from-api.ts
git commit -m "refactor: migrate getRelationshipParent from Handlebars to jsonToGraphQLQuery"
```

---

## Task 9: Migrate `get-groups-from-api.ts` to jsonToGraphQLQuery

**Files:**
- Modify: `src/entities/groups/api/get-groups-from-api.ts`

- [ ] **Step 1: Rewrite `get-groups-from-api.ts`**

Replace the entire file content with:

```typescript
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

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

export interface GetGroupsFromApiParams extends ContextParams {
  objectKind: string;
  objectId: string;
}

export function getGroupsFromApi({
  objectKind,
  objectId,
  branchName,
  atDate,
}: GetGroupsFromApiParams) {
  const query = gql(getObjectGroups({ objectKind }));

  return graphqlClient.query({
    query,
    variables: { ids: [objectId] },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend/app && pnpm build`
Expected: No type errors related to this file.

- [ ] **Step 3: Commit**

```bash
git add src/entities/groups/api/get-groups-from-api.ts
git commit -m "refactor: migrate get-groups-from-api from Handlebars to jsonToGraphQLQuery"
```

---

## Task 10: Remove Handlebars dependency

**Files:**
- Delete: `src/shared/libs/handlebars.ts`
- Modify: `package.json`

- [ ] **Step 1: Delete `src/shared/libs/handlebars.ts`**

```bash
rm src/shared/libs/handlebars.ts
```

- [ ] **Step 2: Verify no remaining Handlebars imports**

```bash
cd frontend/app && grep -r "handlebars" src/ --include="*.ts" --include="*.tsx"
```

Expected: No results.

- [ ] **Step 3: Remove `handlebars` from `package.json`**

Remove the `handlebars` entry from the `dependencies` or `devDependencies` section of `frontend/app/package.json`.

- [ ] **Step 4: Update lockfile**

```bash
cd frontend/app && pnpm install
```

- [ ] **Step 5: Verify full build**

```bash
cd frontend/app && pnpm build
```

Expected: Clean build with no errors.

- [ ] **Step 6: Run lint**

```bash
cd frontend/app && pnpm biome:fix
```

Expected: No lint errors related to imports or unused variables.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: remove Handlebars dependency (no longer used for GraphQL queries)"
```

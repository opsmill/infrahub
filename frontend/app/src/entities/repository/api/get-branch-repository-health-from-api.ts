import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

import { BRANCH_REPOSITORY_FIELDS } from "@/entities/repository/api/get-branch-repositories-from-api";
import type { BranchRepositoryListKind } from "@/entities/repository/domain/model/branch-repository";
import { READONLY_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";

// GraphQL can't OR two attribute filters, so failed imports and unreachable repositories are two
// aliased lists, deduplicated by the caller.
const GET_BRANCH_REPOSITORY_HEALTH = graphql(
  `
  query GET_BRANCH_REPOSITORY_HEALTH(
    $importErrorStatuses: [String]!
    $unreachableStatuses: [String]!
    $syncingStatuses: [String]!
    $limit: Int!
  ) {
    importErrors: CoreGenericRepository(
      sync_status__values: $importErrorStatuses
      limit: $limit
      order: { by: [{ field: "name__value", direction: ASC }] }
    ) {
      count
      edges {
        node {
          ...BranchRepositoryFields
        }
      }
    }
    unreachable: CoreGenericRepository(
      operational_status__values: $unreachableStatuses
      limit: $limit
      order: { by: [{ field: "name__value", direction: ASC }] }
    ) {
      count
      edges {
        node {
          ...BranchRepositoryFields
        }
      }
    }
    syncing: CoreGenericRepository(sync_status__values: $syncingStatuses) {
      count
    }
  }
`,
  [BRANCH_REPOSITORY_FIELDS]
);

const GET_BRANCH_READONLY_REPOSITORY_HEALTH = graphql(
  `
  query GET_BRANCH_READONLY_REPOSITORY_HEALTH(
    $importErrorStatuses: [String]!
    $unreachableStatuses: [String]!
    $syncingStatuses: [String]!
    $limit: Int!
  ) {
    importErrors: CoreReadOnlyRepository(
      sync_status__values: $importErrorStatuses
      limit: $limit
      order: { by: [{ field: "name__value", direction: ASC }] }
    ) {
      count
      edges {
        node {
          ...BranchRepositoryFields
        }
      }
    }
    unreachable: CoreReadOnlyRepository(
      operational_status__values: $unreachableStatuses
      limit: $limit
      order: { by: [{ field: "name__value", direction: ASC }] }
    ) {
      count
      edges {
        node {
          ...BranchRepositoryFields
        }
      }
    }
    syncing: CoreReadOnlyRepository(sync_status__values: $syncingStatuses) {
      count
    }
  }
`,
  [BRANCH_REPOSITORY_FIELDS]
);

type BranchRepositoryHealthConnections =
  | ResultOf<typeof GET_BRANCH_REPOSITORY_HEALTH>
  | ResultOf<typeof GET_BRANCH_READONLY_REPOSITORY_HEALTH>;

export interface GetBranchRepositoryHealthFromApiParams extends BranchContextParams {
  kind: BranchRepositoryListKind;
  importErrorStatuses: string[];
  unreachableStatuses: string[];
  syncingStatuses: string[];
  limit: number;
}

export async function getBranchRepositoryHealthFromApi({
  branchName,
  kind,
  ...variables
}: GetBranchRepositoryHealthFromApiParams): Promise<BranchRepositoryHealthConnections> {
  const context = { branch: branchName, processErrorMessage: () => {} };

  if (kind === READONLY_REPOSITORY_KIND) {
    const { data } = await graphqlClient.query({
      query: GET_BRANCH_READONLY_REPOSITORY_HEALTH,
      variables,
      context,
    });
    return data;
  }

  const { data } = await graphqlClient.query({
    query: GET_BRANCH_REPOSITORY_HEALTH,
    variables,
    context,
  });
  return data;
}

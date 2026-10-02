import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

import type { BranchRepositoryListKind } from "@/entities/repository/domain/model/branch-repository";
import { READONLY_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";

// GraphQL can't OR two attribute filters, so failed imports and unreachable repositories are two
// aliased lists, deduplicated by the caller.
const GET_BRANCH_REPOSITORY_HEALTH = graphql(`
  query GET_BRANCH_REPOSITORY_HEALTH(
    $importErrorStatuses: [String]!
    $unreachableStatuses: [String]!
    $syncingStatuses: [String]!
  ) {
    importErrors: CoreGenericRepository(
      sync_status__values: $importErrorStatuses
      order: { by: [{ field: "name__value", direction: ASC }] }
    ) {
      count
      edges {
        node {
          id
          __typename
          display_label
          name { value }
          commit { value }
          sync_status { value label color description }
          operational_status { value label color }
        }
      }
    }
    unreachable: CoreGenericRepository(
      operational_status__values: $unreachableStatuses
      order: { by: [{ field: "name__value", direction: ASC }] }
    ) {
      count
      edges {
        node {
          id
          __typename
          display_label
          name { value }
          commit { value }
          sync_status { value label color description }
          operational_status { value label color }
        }
      }
    }
    syncing: CoreGenericRepository(sync_status__values: $syncingStatuses) {
      count
    }
  }
`);

const GET_BRANCH_READONLY_REPOSITORY_HEALTH = graphql(`
  query GET_BRANCH_READONLY_REPOSITORY_HEALTH(
    $importErrorStatuses: [String]!
    $unreachableStatuses: [String]!
    $syncingStatuses: [String]!
  ) {
    importErrors: CoreReadOnlyRepository(
      sync_status__values: $importErrorStatuses
      order: { by: [{ field: "name__value", direction: ASC }] }
    ) {
      count
      edges {
        node {
          id
          __typename
          display_label
          name { value }
          commit { value }
          sync_status { value label color description }
          operational_status { value label color }
        }
      }
    }
    unreachable: CoreReadOnlyRepository(
      operational_status__values: $unreachableStatuses
      order: { by: [{ field: "name__value", direction: ASC }] }
    ) {
      count
      edges {
        node {
          id
          __typename
          display_label
          name { value }
          commit { value }
          sync_status { value label color description }
          operational_status { value label color }
        }
      }
    }
    syncing: CoreReadOnlyRepository(sync_status__values: $syncingStatuses) {
      count
    }
  }
`);

export type BranchRepositoryHealthResponse =
  | ResultOf<typeof GET_BRANCH_REPOSITORY_HEALTH>
  | ResultOf<typeof GET_BRANCH_READONLY_REPOSITORY_HEALTH>;

export interface GetBranchRepositoryHealthFromApiParams extends BranchContextParams {
  kind: BranchRepositoryListKind;
  importErrorStatuses: string[];
  unreachableStatuses: string[];
  syncingStatuses: string[];
}

export async function getBranchRepositoryHealthFromApi({
  branchName,
  kind,
  ...variables
}: GetBranchRepositoryHealthFromApiParams): Promise<BranchRepositoryHealthResponse> {
  const context = { branch: branchName };

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

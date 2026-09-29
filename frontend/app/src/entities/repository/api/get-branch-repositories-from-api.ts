import { CombinedError } from "@urql/core";

import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

import type { BranchRepositoryListKind } from "@/entities/repository/domain/model/branch-repository";
import {
  READONLY_REPOSITORY_KIND,
  REPOSITORY_FETCH_LIMIT,
} from "@/entities/repository/domain/model/repository";

const GET_BRANCH_REPOSITORIES = graphql(`
  query GET_BRANCH_REPOSITORIES($limit: Int!) {
    CoreGenericRepository(limit: $limit) {
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
  }
`);

const GET_BRANCH_READONLY_REPOSITORIES = graphql(`
  query GET_BRANCH_READONLY_REPOSITORIES($limit: Int!) {
    CoreReadOnlyRepository(limit: $limit) {
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
  }
`);

export type BranchRepositoriesConnection =
  | ResultOf<typeof GET_BRANCH_REPOSITORIES>["CoreGenericRepository"]
  | ResultOf<typeof GET_BRANCH_READONLY_REPOSITORIES>["CoreReadOnlyRepository"];

export type BranchRepositoryNode = NonNullable<
  NonNullable<BranchRepositoriesConnection["edges"][number]>["node"]
>;

export interface GetBranchRepositoriesFromApiParams extends BranchContextParams {
  kind: BranchRepositoryListKind;
}

export interface GetBranchRepositoriesFromApiResult {
  data: BranchRepositoriesConnection | undefined;
  errors?: ReadonlyArray<{ message: string; extensions?: unknown }>;
}

async function fetchConnection({
  branchName,
  kind,
}: GetBranchRepositoriesFromApiParams): Promise<BranchRepositoriesConnection> {
  const context = { branch: branchName };
  const variables = { limit: REPOSITORY_FETCH_LIMIT };

  if (kind === READONLY_REPOSITORY_KIND) {
    const { data } = await graphqlClient.query({
      query: GET_BRANCH_READONLY_REPOSITORIES,
      variables,
      context,
    });
    return data.CoreReadOnlyRepository;
  }

  const { data } = await graphqlClient.query({
    query: GET_BRANCH_REPOSITORIES,
    variables,
    context,
  });
  return data.CoreGenericRepository;
}

// The shared client throws on GraphQL errors; the caller needs their extensions to tell a
// permission denial from a failure, so they are handed back instead of thrown.
export async function getBranchRepositoriesFromApi(
  params: GetBranchRepositoriesFromApiParams
): Promise<GetBranchRepositoriesFromApiResult> {
  try {
    return { data: await fetchConnection(params) };
  } catch (error) {
    if (error instanceof Error && error.cause instanceof CombinedError) {
      return { data: undefined, errors: error.cause.graphQLErrors };
    }
    throw error;
  }
}

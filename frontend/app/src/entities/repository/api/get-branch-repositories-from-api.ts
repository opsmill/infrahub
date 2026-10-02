import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

import type { BranchRepositoryListKind } from "@/entities/repository/domain/model/branch-repository";
import { READONLY_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";

const GET_BRANCH_REPOSITORIES = graphql(`
  query GET_BRANCH_REPOSITORIES($limit: Int!, $offset: Int!) {
    CoreGenericRepository(
      limit: $limit
      offset: $offset
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
  }
`);

const GET_BRANCH_READONLY_REPOSITORIES = graphql(`
  query GET_BRANCH_READONLY_REPOSITORIES($limit: Int!, $offset: Int!) {
    CoreReadOnlyRepository(
      limit: $limit
      offset: $offset
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
  }
`);

export type BranchRepositoriesConnection =
  | ResultOf<typeof GET_BRANCH_REPOSITORIES>["CoreGenericRepository"]
  | ResultOf<typeof GET_BRANCH_READONLY_REPOSITORIES>["CoreReadOnlyRepository"];

export interface GetBranchRepositoriesFromApiParams extends BranchContextParams {
  kind: BranchRepositoryListKind;
  limit: number;
  offset: number;
}

export async function getBranchRepositoriesFromApi({
  branchName,
  kind,
  limit,
  offset,
}: GetBranchRepositoriesFromApiParams): Promise<BranchRepositoriesConnection> {
  const context = { branch: branchName };
  const variables = { limit, offset };

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

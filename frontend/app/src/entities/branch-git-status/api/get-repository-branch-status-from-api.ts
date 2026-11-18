import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";

const GET_REPOSITORY_BRANCH_STATUS = graphql(`
  query GET_REPOSITORY_BRANCH_STATUS($id: String!, $limit: Int!) {
    InfrahubRepositoryBranchStatus(id: $id, limit: $limit) {
      count
      edges {
        node {
          name { value }
          commit { value }
          sync_status {
            value
            label
            color
            description
          }
        }
      }
    }
  }
`);

export type RepositoryBranchStatusConnection = ResultOf<
  typeof GET_REPOSITORY_BRANCH_STATUS
>["InfrahubRepositoryBranchStatus"];

export interface GetRepositoryBranchStatusFromApiParams {
  id: string;
  limit: number;
}

export async function getRepositoryBranchStatusFromApi({
  id,
  limit,
}: GetRepositoryBranchStatusFromApiParams): Promise<RepositoryBranchStatusConnection> {
  const { data } = await graphqlClient.query({
    query: GET_REPOSITORY_BRANCH_STATUS,
    variables: { id, limit },
    context: { processErrorMessage: () => {} },
  });
  return data.InfrahubRepositoryBranchStatus;
}

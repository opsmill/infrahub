import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";

const GET_BRANCH_GIT_REPOSITORIES = graphql(`
  query GET_BRANCH_GIT_REPOSITORIES($limit: Int!, $offset: Int!) {
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
          name { value }
        }
      }
    }
  }
`);

export type BranchGitRepositoriesConnection = ResultOf<
  typeof GET_BRANCH_GIT_REPOSITORIES
>["CoreGenericRepository"];

export interface GetBranchGitRepositoriesFromApiParams {
  limit: number;
  offset: number;
}

export async function getBranchGitRepositoriesFromApi({
  limit,
  offset,
}: GetBranchGitRepositoriesFromApiParams): Promise<BranchGitRepositoriesConnection> {
  const { data } = await graphqlClient.query({
    query: GET_BRANCH_GIT_REPOSITORIES,
    variables: { limit, offset },
    context: { processErrorMessage: () => {} },
  });
  return data.CoreGenericRepository;
}

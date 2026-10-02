import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const GET_REPOSITORY_NAMES = graphql(`
  query GET_REPOSITORY_NAMES($ids: [ID]!) {
    CoreGenericRepository(ids: $ids) {
      edges {
        node {
          id
          display_label
          name { value }
        }
      }
    }
  }
`);

export interface GetRepositoryNamesFromApiParams extends BranchContextParams {
  ids: string[];
}

export async function getRepositoryNamesFromApi({
  branchName,
  ids,
}: GetRepositoryNamesFromApiParams): Promise<Record<string, string>> {
  const { data } = await graphqlClient.query({
    query: GET_REPOSITORY_NAMES,
    variables: { ids },
    context: { branch: branchName },
  });

  return Object.fromEntries(
    data.CoreGenericRepository.edges.flatMap((edge) => {
      const node = edge?.node;
      const name = node?.name?.value || node?.display_label;
      return node?.id && name ? [[node.id, name]] : [];
    })
  );
}

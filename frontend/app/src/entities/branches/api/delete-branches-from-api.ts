import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export type DeleteBranchesFromApiParams = {
  names: string[];
};

export type DeleteBranchesFromApiResult = {
  deleted: string[];
  failed: string[];
};

const getDeleteBranchesQuery = (names: string[]) => {
  const mutations = names.reduce((acc, name, index) => {
    return {
      ...acc,
      [`branch${index}`]: {
        __aliasFor: "BranchDelete",
        __args: {
          data: { name },
        },
        ok: true,
      },
    };
  }, {});

  const query = {
    mutation: mutations,
  };

  return jsonToGraphQLQuery(query);
};

export async function deleteBranchesFromApi(
  params: DeleteBranchesFromApiParams
): Promise<DeleteBranchesFromApiResult> {
  try {
    const { data } = await graphqlClient.mutate({
      mutation: gql(getDeleteBranchesQuery(params.names)),
    });

    const deleted = params.names.filter((_, index) => data?.[`branch${index}`]?.ok);
    const failed = params.names.filter((_, index) => !data?.[`branch${index}`]?.ok);

    return { deleted, failed };
  } catch {
    return { deleted: [], failed: params.names };
  }
}

import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

export interface CreateObjectFromApiApiParams extends BranchContextParams {
  objectKind: string;
  data: Record<string, any>;
  profileIds?: Array<string>;
}

export function createObjectFromApi({
  data,
  objectKind,
  profileIds = [],
  branchName,
}: CreateObjectFromApiApiParams) {
  const mutation = jsonToGraphQLQuery({
    mutation: {
      [`${objectKind}Create`]: {
        __args: {
          data: {
            ...data,
            ...(profileIds?.length
              ? { profiles: profileIds.map((profileId) => ({ id: profileId })) }
              : {}),
          },
        },
        object: {
          id: true,
          display_label: true,
          hfid: true,
          __typename: true,
        },
      },
    },
  });

  return graphqlClient.mutate({
    mutation: gql(mutation),
    context: {
      branch: branchName,
    },
  });
}

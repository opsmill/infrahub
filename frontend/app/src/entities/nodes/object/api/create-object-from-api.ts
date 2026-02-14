import { gql } from "@apollo/client";
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

export interface CreateObjectFromApiParams extends BranchContextParams {
  objectKind: string;
  data: Record<string, unknown>;
  profileIds?: Array<string>;
  file?: File;
}

function buildProfiles(profileIds: Array<string>) {
  return profileIds.map((id) => ({ id }));
}

export function createObjectFromApi({
  data,
  objectKind,
  profileIds = [],
  branchName,
  file,
}: CreateObjectFromApiParams) {
  const mutation = jsonToGraphQLQuery({
    mutation: {
      ...(file && { __variables: { file: "Upload!" } }),
      [`${objectKind}Create`]: {
        __args: {
          data: {
            ...data,
            ...(profileIds.length && { profiles: buildProfiles(profileIds) }),
          },
          ...(file && { file: new VariableType("file") }),
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
    variables: file ? { file } : undefined,
    context: {
      branch: branchName,
    },
  });
}

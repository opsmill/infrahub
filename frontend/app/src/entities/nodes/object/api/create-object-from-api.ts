import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

export interface CreateObjectFromApiParams extends BranchContextParams {
  objectKind: string;
  data: Record<string, unknown>;
  profileIds?: Array<string>;
  file?: File;
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
            ...(profileIds.length && { profiles: profileIds.map((id) => ({ id })) }),
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
    mutation: graphql(mutation),
    variables: file ? { file } : undefined,
    context: {
      branch: branchName,
    },
  });
}

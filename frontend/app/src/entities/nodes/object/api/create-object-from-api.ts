import { gql } from "@apollo/client";
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

import { hoistAttributeValuesToVariables } from "@/entities/nodes/object/utils/hoist-attribute-values-to-variables";

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
  const {
    data: hoistedData,
    variableDefinitions,
    variableValues,
  } = hoistAttributeValuesToVariables(data);
  const hasVariables = file !== undefined || Object.keys(variableDefinitions).length > 0;

  const mutation = jsonToGraphQLQuery({
    mutation: {
      ...(hasVariables && {
        __variables: { ...(file && { file: "Upload!" }), ...variableDefinitions },
      }),
      [`${objectKind}Create`]: {
        __args: {
          data: {
            ...hoistedData,
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
    mutation: gql(mutation),
    variables: hasVariables ? { ...(file && { file }), ...variableValues } : undefined,
    context: {
      branch: branchName,
    },
  });
}

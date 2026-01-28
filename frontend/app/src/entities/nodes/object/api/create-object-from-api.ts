import { gql } from "@apollo/client";
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

export interface CreateObjectFromApiApiParams extends BranchContextParams {
  objectKind: string;
  data: Record<string, any>;
  profileIds?: Array<string>;
  file?: File;
}

export function createObjectFromApi({
  data,
  objectKind,
  profileIds = [],
  branchName,
  file,
}: CreateObjectFromApiApiParams) {
  const hasFile = file !== undefined;

  const mutationArgs: Record<string, unknown> = {
    data: {
      ...data,
      ...(profileIds?.length
        ? { profiles: profileIds.map((profileId) => ({ id: profileId })) }
        : {}),
    },
  };

  // For file uploads, use a GraphQL variable
  if (hasFile) {
    mutationArgs.file = new VariableType("file");
  }

  const mutationContent: Record<string, unknown> = {
    [`${objectKind}Create`]: {
      __args: mutationArgs,
      object: {
        id: true,
        display_label: true,
        hfid: true,
        __typename: true,
      },
    },
  };

  // Add variable definitions for file uploads
  if (hasFile) {
    mutationContent.__variables = {
      file: "Upload!",
    };
  }

  const mutationDef = {
    mutation: mutationContent,
  };

  const mutation = jsonToGraphQLQuery(mutationDef);

  return graphqlClient.mutate({
    mutation: gql(mutation),
    variables: hasFile ? { file } : undefined,
    context: {
      branch: branchName,
    },
  });
}

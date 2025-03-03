import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

const getObjectsCountQuery = (kind: string) => {
  const query = {
    query: {
      __name: `GetObjectsCount${kind}`,
      [kind]: {
        count: true,
      },
    },
  };

  return gql(jsonToGraphQLQuery(query));
};

export type GetObjectsCountFromApiParams = ContextParams & { schemaKind: string };

export const getObjectsCountFromApi = async ({
  schemaKind,
  branchName,
  atDate,
}: GetObjectsCountFromApiParams) => {
  return graphqlClient.query({
    query: getObjectsCountQuery(schemaKind),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};

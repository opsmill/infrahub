import { NODE_TRIGGER_RULE } from "@/entities/triggers/constants";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

export type GetMatchParentParams = ContextParams & {
  objectId: string;
};

export const getMatchParentFromApi = async ({
  branchName,
  atDate,
  objectId,
}: GetMatchParentParams) => {
  const queryString = jsonToGraphQLQuery({
    query: {
      __name: "GetMatchParent",
      [NODE_TRIGGER_RULE]: {
        __args: {
          matches__ids: [objectId],
        },
        edges: {
          node: {
            id: true,
            node_kind: {
              value: true,
            },
          },
        },
      },
    },
  });

  const query = gql(queryString);

  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};

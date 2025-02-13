import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";
import { INFRAHUB_EVENT, NODE_MUTATED_EVENT } from "../utils/constants";

const getGlobalEventsQuery = () => {
  const request = {
    query: {
      __name: "GET_GLOBAL_EVENTS",
      [INFRAHUB_EVENT]: {
        count: true,
        edges: {
          node: {
            id: true,
            event: true,
            branch: true,
            account_id: true,
            occurred_at: true,
            __on: {
              __typeName: NODE_MUTATED_EVENT,
              attributes: {
                action: true,
                kind: true,
                name: true,
                value: true,
                value_previous: true,
              },
              payload: true,
            },
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};

export function getGlobalEventsFromApi({
  branchName,
  atDate,
}: { branchName: string; atDate: Date | null }) {
  return graphqlClient.query({
    query: gql(getGlobalEventsQuery()),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}

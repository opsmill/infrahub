import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";
import { INFRAHUB_EVENT, NODE_MUTATED_EVENT } from "../utils/constants";

const getActivitiesQuery = ({ ids }: { ids?: Array<string | undefined> }) => {
  const request = {
    query: {
      __name: "GET_ACTIVITIES",
      [INFRAHUB_EVENT]: {
        __args: {
          related_node__ids: ids,
        },
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

export function getEventsFromApi({
  ids,
  branchName,
  atDate,
}: { ids?: Array<string | undefined>; branchName: string; atDate: Date | null }) {
  return graphqlClient.query({
    query: gql(getActivitiesQuery({ ids })),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}

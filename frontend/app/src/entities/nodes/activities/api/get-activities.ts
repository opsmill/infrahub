import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";
import { NODE_MUTATED_EVENT } from "../utils/constants";

export const OBJECTS_PER_PAGE = 40;

const getActivitiesQuery = () => {
  const query = {
    InfrahubEvent: {
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
  };

  return jsonToGraphQLQuery(query);
};

export function getActivitiesFromApi({
  branchName,
  atDate,
}: { branchName: string; atDate: Date | null }) {
  return graphqlClient.query({
    query: gql(getActivitiesQuery()),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}

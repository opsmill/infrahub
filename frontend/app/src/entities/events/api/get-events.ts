import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";

const EVENTS_QUERY = `
  query GET_ACTIVITIES($ids: [String], $limit: Int) {
    InfrahubEvent(related_node__ids: $ids, limit: $limit) {
      count
      edges {
        node {
          id
          event
          branch
          occurred_at
          level
          account_id
          primary_node {
            id
            kind
          }
          __typename
          ... on NodeMutatedEvent {
            attributes {
              action
              kind
              name
              value
              value_previous
            }
            payload
          }
        }
      }
    }
  }
`;

export function getEventsFromApi({
  ids,
  limit,
  branchName,
  atDate,
}: { ids?: Array<string | undefined>; limit?: number; branchName: string; atDate: Date | null }) {
  return graphqlClient.query({
    query: gql(EVENTS_QUERY),
    variables: {
      ids,
      limit,
    },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}

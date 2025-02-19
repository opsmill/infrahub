import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";

const EVENTS_QUERY = gql`
  query GET_ACTIVITIES($ids: [String!], $offset: Int, $limit: Int) {
    InfrahubEvent(related_node__ids: $ids, offset: $offset, limit: $limit) {
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
  offset,
  limit,
  search,
  branchName,
  atDate,
}: {
  ids?: Array<string | undefined>;
  offset?: number;
  limit?: number;
  search?: string;
  branchName: string;
  atDate: Date | null;
}) {
  return graphqlClient.query({
    query: EVENTS_QUERY,
    variables: {
      ids,
      offset,
      limit,
      search,
    },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}

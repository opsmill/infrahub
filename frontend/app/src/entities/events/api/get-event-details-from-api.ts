import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";

const EVENT_DETAILS_QUERY = gql`
  query GET_ACTIVITY_DETAILS($ids: [String!]) {
    InfrahubEvent(ids: $ids) {
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
          related_nodes {
            id
            kind
          }
          has_children
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

export type GetEventDetailsFromApiParams = {
  id: string;
};

export async function getEventDetailsFromApi({ id }: GetEventDetailsFromApiParams) {
  return graphqlClient.query({
    query: EVENT_DETAILS_QUERY,
    variables: {
      ids: [id],
    },
  });
}

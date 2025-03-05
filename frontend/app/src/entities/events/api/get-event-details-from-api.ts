import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";
import { INFRAHUB_EVENT } from "../constants";
import { EventType } from "@/entities/events/types";

export type EventDetailsFilters = {
  id: string;
};

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

export async function getEventDetailsFromApi({
  branchName,
  atDate,
  id,
  ...filters
}: EventDetailsFilters & { branchName?: string; atDate?: Date | null }) {
  const { data } = await graphqlClient.query({
    query: EVENT_DETAILS_QUERY,
    variables: {
      ids: [id],
      ...filters,
    },
    context: {
      branch: branchName,
      date: atDate,
    },
  });

  const activities: EventType[] = data?.[INFRAHUB_EVENT]?.edges?.map((edge) => {
    return edge.node;
  });

  return activities[0];
}

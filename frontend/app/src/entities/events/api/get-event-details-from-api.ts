import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";
import { EventType } from "../ui/event";
import { INFRAHUB_EVENT } from "../utils/constants";

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
  ...filters
}: EventDetailsFilters & { branchName?: string; atDate?: Date | null }) {
  const { data } = await graphqlClient.query({
    query: EVENT_DETAILS_QUERY,
    variables: {
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

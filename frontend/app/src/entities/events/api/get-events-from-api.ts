import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";
import { EventType } from "../ui/event";
import { INFRAHUB_EVENT } from "../utils/constants";

export type GlobalEventsFilters = {
  hasChildren?: boolean;
  eventType?: Array<string>;
  primaryNodeIds?: Array<string>;
  relatedNodeIds?: Array<string>;
  parentIds?: Array<string>;
  accountIds?: Array<string>;
  level?: number;
  since?: Date;
  until?: Date;
  offset?: number;
  limit?: number;
};

const EVENTS_QUERY = gql`
  query GET_ACTIVITIES(
    $hasChildren: Boolean
    $branches: [String!]
    $eventType: [String!]
    $primaryNodeIds: [String!]
    $relatedNodeIds: [String!]
    $parentIds: [String!]
    $accountIds: [String!]
    $level: Int
    $since: DateTime
    $until: DateTime
    $offset: Int
    $limit: Int
  ) {
    InfrahubEvent(
      has_children: $hasChildren
      branches: $branches
      event_type: $eventType
      primary_node__ids: $primaryNodeIds
      related_node__ids: $relatedNodeIds
      parent__ids: $parentIds
      account__ids: $accountIds
      level: $level
      since: $since
      until: $until
      offset: $offset
      limit: $limit
    ) {
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

export async function getEventsFromApi({
  branchName,
  atDate,
  ...filters
}: GlobalEventsFilters & { branchName?: string; atDate?: Date | null }) {
  const { data } = await graphqlClient.query({
    query: EVENTS_QUERY,
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

  const count = data?.data?.[INFRAHUB_EVENT]?.count;

  return {
    activities,
    count,
  };
}

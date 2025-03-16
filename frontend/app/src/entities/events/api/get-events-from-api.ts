import { Get_ActivitiesQuery } from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { PaginationParams } from "@/shared/api/types";
import { gql } from "@apollo/client";

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

export const OBJECTS_PER_PAGE = 40;

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
          ... on StandardEvent {
            payload
          }
            ... on BranchCreatedEvent {
            payload
            created_branch
          }
          ... on BranchDeletedEvent {
            payload
            deleted_branch
          }
          ... on BranchRebasedEvent {
            payload
            rebased_branch
          }
            ... on BranchMergedEvent {
            source_branch
          }
          ... on GroupEvent {
            ancestors {
              id
              kind
            }
            members {
              id
              kind
            }
          }
          ... on GroupEvent {
            ancestors {
              id
              kind
            }
            members {
              id
              kind
            }
          }
        }
      }
    }
  }
`;

export type GetEventsFromApiParams = PaginationParams & { filters: GlobalEventsFilters };

export async function getEventsFromApi({
  limit = OBJECTS_PER_PAGE,
  filters,
}: GetEventsFromApiParams) {
  return graphqlClient.query<Get_ActivitiesQuery>({
    query: EVENTS_QUERY,
    variables: {
      limit,
      ...filters,
    },
  });
}

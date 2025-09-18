import { gql } from "@apollo/client";

import type { Get_Infrahub_EventsQuery } from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { PaginationParams } from "@/shared/api/types";

export type GlobalEventsFilters = {
  ids?: Array<string>;
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
  order?: string;
};

export const OBJECTS_PER_PAGE = 40;

export const EVENTS_QUERY = gql`
  query GET_INFRAHUB_EVENTS(
    $ids: [String!]
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
    $order: EventSortOrder
  ) {
    InfrahubEvent(
      ids: $ids
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
      order: $order
    ) {
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
            relationships {
              action
              name
              peer {
                id
                kind
              }
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
          ... on ArtifactEvent {
            checksum
            storage_id
            artifact_definition_id
            checksum_previous
            storage_id_previous
          }
        }
      }
    }
  }
`;

export interface GetEventsFromApiParams extends PaginationParams {
  filters: GlobalEventsFilters;
}

export async function getEventsFromApi({
  limit = OBJECTS_PER_PAGE,
  offset,
  filters,
}: GetEventsFromApiParams) {
  return graphqlClient.query<Get_Infrahub_EventsQuery>({
    query: EVENTS_QUERY,
    variables: {
      limit,
      offset,
      ...filters,
    },
  });
}

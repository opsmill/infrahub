import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const OBJECTS_PER_PAGE = 40;

const EVENTS_QUERY = graphql(`
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
`);

export interface GetEventsFromApiParams extends VariablesOf<typeof EVENTS_QUERY> {}

export async function getEventsFromApi({
  limit = OBJECTS_PER_PAGE,
  offset,
  ...filters
}: GetEventsFromApiParams) {
  return graphqlClient.query({
    query: EVENTS_QUERY,
    variables: {
      limit,
      offset,
      ...filters,
    },
  });
}

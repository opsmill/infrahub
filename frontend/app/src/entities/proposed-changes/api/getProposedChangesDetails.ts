import { gql } from "@apollo/client";

export const GET_PROPOSED_CHANGE_DETAILS = gql`
  query GET_PROPOSED_CHANGE_DETAILS($id: ID, $nodeId: String, $state: String) {
    CoreProposedChange(ids: [$id], state__value: $state) {
      count
      edges {
        node {
          id
          display_label
          _updated_at
          name {
            value
          }
          description {
            value
            updated_at
          }
          source_branch {
            value
          }
          destination_branch {
            value
          }
          state {
            value
          }
          approved_by {
            edges {
              node {
                id
                display_label
              }
            }
          }
          reviewers {
            edges {
              node {
                id
                display_label
              }
            }
          }
          created_by {
            node {
              id
              display_label
            }
          }
          comments {
            count
          }
          created_by {
            node {
              id
              display_label
            }
          }
        }
      }
    }
    InfrahubTask(related_node__ids: [$nodeId]) {
      count
    }
  }
`;

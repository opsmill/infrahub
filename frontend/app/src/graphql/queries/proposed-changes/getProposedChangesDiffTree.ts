import { gql } from "@apollo/client";

export const getProposedChangesDiffTree = gql`
  query GET_PROPOSED_CHANGES_DIFF_TREE($branch: String, $filters: DiffTreeQueryFilters) {
    DiffTree(branch: $branch, filters: $filters) {
      nodes {
        uuid
        relationships {
          label
          status
          contains_conflict
          elements {
            conflict {
              base_branch_action
              base_branch_changed_at
              base_branch_value
              diff_branch_action
              diff_branch_changed_at
              diff_branch_value
              selected_branch
              uuid
            }
            last_changed_at
            contains_conflict
            peer_id
            properties {
              conflict {
                base_branch_action
                base_branch_changed_at
                base_branch_value
                diff_branch_action
                diff_branch_changed_at
                diff_branch_value
                selected_branch
                uuid
              }
              last_changed_at
              new_value
              previous_value
              property_type
              status
              path_identifier
            }
            status
            path_identifier
            peer_label
          }
          last_changed_at
          name
          path_identifier
        }
        conflict {
          base_branch_action
          base_branch_changed_at
          diff_branch_action
          base_branch_value
          diff_branch_changed_at
          diff_branch_value
          selected_branch
          uuid
        }
        attributes {
          contains_conflict
          last_changed_at
          name
          properties {
            conflict {
              base_branch_action
              base_branch_changed_at
              base_branch_value
              diff_branch_action
              diff_branch_changed_at
              diff_branch_value
              selected_branch
              uuid
            }
            last_changed_at
            new_value
            previous_value
            property_type
            status
            path_identifier
          }
          status
          path_identifier
        }
        kind
        contains_conflict
        label
        last_changed_at
        status
        parent_node
        path_identifier
      }
      to_time
      base_branch
      diff_branch
      from_time
    }
  }
`;

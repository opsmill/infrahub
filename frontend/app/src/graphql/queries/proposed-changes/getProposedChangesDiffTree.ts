export const getProposedChangesDiffTree = `
query GET_PROPOSED_CHANGES_DIFF_TREE($branch: String) {
  DiffTree(branch: $branch) {
    nodes {
      uuid
      relationships {
        label
        status
        node_uuids
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
          num_added
          num_conflicts
          num_removed
          num_updated
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
          }
          status
        }
        last_changed_at
        name
        num_added
        num_conflicts
        num_removed
        num_updated
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
        num_added
        num_conflicts
        num_removed
        num_updated
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
        }
        status
      }
      kind
      contains_conflict
      label
      last_changed_at
      num_added
      num_conflicts
      num_removed
      num_updated
      status
    }
    num_added
    num_conflicts
    num_removed
    num_updated
    to_time
    base_branch
    diff_branch
    from_time
  }
}
`;

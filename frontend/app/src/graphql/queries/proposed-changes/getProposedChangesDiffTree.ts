export const getProposedChangesDiffTree = `
query GET_PROPOSED_CHANGES_DIFF_TREE($branch: String) {
  DiffTree (branch: $branch) {
    nodes {
      label
      contains_conflict
      kind
      last_changed_at
      num_added
      num_conflicts
      num_removed
      num_updated
      status
      uuid
      relationships {
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
          contains_conflict
          last_changed_at
          num_added
          num_conflicts
          num_removed
          num_updated
          peer_id
          properties {
            last_changed_at
            new_value
            previous_value
            property_type
            status
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
          }
          status
        }
        last_changed_at
        name
        node_uuids
        num_added
        num_conflicts
        num_removed
        num_updated
        status
      }
    }
  }
}
`;

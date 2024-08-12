export const getProposedChangesDiffSummary = `
query GET_PROPOSED_CHANGES_DIFF_SUMMARY {
  DiffTree {
    num_added
    num_updated
    num_removed
    num_conflicts
  }
}
`;

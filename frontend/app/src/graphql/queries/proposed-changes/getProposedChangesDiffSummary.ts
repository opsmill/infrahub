export const getProposedChangesDiffSummary = `
query GET_PROPOSED_CHANGES_DIFF_SUMMARY($branch: String) {
  DiffTree(branch: $branch) {
    num_added
    num_updated
    num_removed
    num_conflicts
  }
}
`;

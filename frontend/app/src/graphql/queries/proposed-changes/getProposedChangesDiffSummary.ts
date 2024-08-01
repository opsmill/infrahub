export const getProposedChangesDiffSummary = `
query GET_PROPOSED_CHANGES_DIFF_SUMMARY($branch: String) {
  DiffSummary(diff_from: $branch){
    display_label
  }
}
`;

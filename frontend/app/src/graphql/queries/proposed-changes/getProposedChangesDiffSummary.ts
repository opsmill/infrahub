export const getProposedChangesDiffSummary = `
query GET_PROPOSED_CHANGES_DIFF_SUMMARY($timeFrom: String) {
  DiffSummary(time_from: $timeFrom){
    elements{
      summary{
        added
        updated
        removed
      }
    }
  }
}
`;

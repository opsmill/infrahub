export const getProposedChangesDiffSummary = `
query GET_PROPOSED_CHANGES_DIFF_SUMMARY {
  DiffSummary{
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

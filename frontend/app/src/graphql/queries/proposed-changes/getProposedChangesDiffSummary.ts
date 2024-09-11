import { gql } from "@apollo/client";

export const getProposedChangesDiffSummary = gql`
  query GET_PROPOSED_CHANGES_DIFF_SUMMARY($branch: String) {
    DiffTreeSummary(branch: $branch) {
      num_added
      num_updated
      num_removed
      num_conflicts
    }
  }
`;

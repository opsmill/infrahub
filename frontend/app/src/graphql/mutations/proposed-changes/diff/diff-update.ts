import { gql } from "@apollo/client";

export const DIFF_UPDATE = gql`
  mutation DIFF_UPDATE($branchName: String!, $wait: Boolean) {
    DiffUpdate(data: { branch: $branchName, wait_for_completion: $wait }) {
      ok
    }
  }
`;

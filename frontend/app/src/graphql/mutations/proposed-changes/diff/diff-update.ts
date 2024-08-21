import { gql } from "@apollo/client";

export const DIFF_UPDATE = gql`
  mutation DIFF_UPDATE($branchName: String!) {
    DiffUpdate(data: { branch: $branchName }) {
      ok
    }
  }
`;

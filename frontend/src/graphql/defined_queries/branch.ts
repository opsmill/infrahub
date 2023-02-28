import { gql } from "@apollo/client";
import { Branch } from "../../generated/graphql";

export interface iBranchData {
  branch: Array<Branch>;
}

export const BRANCH_QUERY = gql`
  query Branch {
    branch {
      id
      name
      created_at
      is_data_only
      is_default
    }
  }
`;

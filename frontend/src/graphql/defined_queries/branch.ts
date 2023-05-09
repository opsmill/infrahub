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
      description
      origin_branch
      branched_from
      created_at
      is_data_only
      is_default
    }
  }
`;

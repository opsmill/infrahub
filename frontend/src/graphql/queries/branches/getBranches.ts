import { gql } from "@apollo/client";
import { Branch } from "../../../generated/graphql";

export interface iBranchData {
  branch: Array<Branch>;
}

const GET_BRANCHES = gql`
  query GetBranches {
    Branch {
      id
      name
      description
      origin_branch
      branched_from
      created_at
      is_data_only
      is_default
      is_isolated
      has_schema_changes
    }
  }
`;

export default GET_BRANCHES;

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
    }
  }
`;

export default GET_BRANCHES;

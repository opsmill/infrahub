import { gql } from "@apollo/client";

const GET_BRANCHES = gql`
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

export default GET_BRANCHES;
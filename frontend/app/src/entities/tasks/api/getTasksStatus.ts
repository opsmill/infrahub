import { gql } from "@apollo/client";

export const TASKS_STATUS = gql`
query TASKS_STATUS($branch: String!) {
  InfrahubTaskBranchStatus(branch: $branch){
    count
  }
}
`;

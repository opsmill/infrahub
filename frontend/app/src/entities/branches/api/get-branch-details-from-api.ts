import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

const GET_BRANCH_DETAILS = graphql(`
  query GetBranchDetails($branchName: String!) {
    InfrahubBranch(name__value: $branchName) {
      edges {
        node {
          id
          name {
            value
          }
          description {
            value
          }
          origin_branch {
            value
          }
          branched_from {
            value
          }
          status {
            value
          }
          created_at
          sync_with_git {
            value
          }
          is_default {
            value
          }
          has_schema_changes {
            value
          }
        }
      }
    }
  }
`);

export interface GetBranchDetailsFromApiParams extends BranchContextParams {}

export function getBranchDetailsFromApi({ branchName }: GetBranchDetailsFromApiParams) {
  return graphqlClient.query({
    query: GET_BRANCH_DETAILS,
    variables: { branchName },
  });
}

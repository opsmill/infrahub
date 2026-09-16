import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

// The backend rejects `sync_status__value`, `internal_status__value` and `own_values_only` with a
// ValidationError for as long as the resolver serves placeholder values.
const REPOSITORY_BRANCH_STATUS = graphql(`
  query REPOSITORY_BRANCH_STATUS(
    $id: String!
    $limit: Int
    $offset: Int
    $name__value: String
    $partial_match: Boolean
    $status__value: BranchStatus
  ) {
    InfrahubRepositoryBranchStatus(
      id: $id
      limit: $limit
      offset: $offset
      name__value: $name__value
      partial_match: $partial_match
      status__value: $status__value
    ) {
      count
      edges {
        node {
          name {
            value
          }
          is_default {
            value
          }
          commit {
            value
          }
          sync_status {
            value
            label
            color
            description
          }
          ref {
            value
          }
        }
      }
    }
  }
`);

export interface GetRepositoryBranchStatusFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof REPOSITORY_BRANCH_STATUS> {}

export function getRepositoryBranchStatusFromApi({
  branchName,
  ...variables
}: GetRepositoryBranchStatusFromApiParams) {
  return graphqlClient.query({
    query: REPOSITORY_BRANCH_STATUS,
    variables,
    context: {
      branch: branchName,
    },
  });
}

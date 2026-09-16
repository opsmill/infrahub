import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

// `sync_status__value`, `internal_status__value` and `own_values_only` are deliberately not
// declared: the backend rejects all three with a ValidationError while the resolver serves
// placeholder values, and `node_metadata` is not selected so no `updated_at` can reach the card.
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
          status {
            value
          }
          is_default {
            value
          }
          sync_with_git {
            value
          }
          branched_from {
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
          internal_status {
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

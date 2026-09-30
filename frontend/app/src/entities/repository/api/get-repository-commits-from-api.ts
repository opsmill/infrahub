import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const REPOSITORY_COMMITS = graphql(`
  query REPOSITORY_COMMITS($repositoryId: String!, $limit: Int, $offset: Int) {
    InfrahubRepositoryCommits(repository_id: $repositoryId, limit: $limit, offset: $offset) {
      repository_id
      branch_name
      git_ref
      condition
      imported_commit
      remote_head
      pending_count
      fetched_at
      checked_at
      unavailable {
        reason
        message
      }
      edges {
        node {
          hash
          short_hash
          summary
          author_name
          authored_at
          state
        }
      }
    }
  }
`);

export interface GetRepositoryCommitsFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof REPOSITORY_COMMITS> {}

export function getRepositoryCommitsFromApi({
  repositoryId,
  limit,
  offset,
  branchName,
}: GetRepositoryCommitsFromApiParams) {
  return graphqlClient.query({
    query: REPOSITORY_COMMITS,
    variables: {
      repositoryId,
      limit,
      offset,
    },
    context: {
      branch: branchName,
    },
  });
}

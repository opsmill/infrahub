import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const REPOSITORY_COMMIT_STATUS = graphql(`
  query REPOSITORY_COMMIT_STATUS($repositoryId: String!) {
    InfrahubRepositoryCommits(repository_id: $repositoryId, limit: 1) {
      condition
      pending_count
    }
  }
`);

export interface GetRepositoryCommitStatusFromApiParams extends BranchContextParams {
  repositoryId: string;
}

export function getRepositoryCommitStatusFromApi({
  repositoryId,
  branchName,
}: GetRepositoryCommitStatusFromApiParams) {
  return graphqlClient.query({
    query: REPOSITORY_COMMIT_STATUS,
    variables: { repositoryId },
    context: { branch: branchName },
  });
}

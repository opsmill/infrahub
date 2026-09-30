import {
  type GetRepositoryCommitsFromApiParams,
  getRepositoryCommitsFromApi,
} from "@/entities/repository/api/get-repository-commits-from-api";
import type {
  RepositoryCommit,
  RepositoryCommitLog,
} from "@/entities/repository/domain/model/repository";

export type GetRepositoryCommitsParams = GetRepositoryCommitsFromApiParams;

export type GetRepositoryCommitsResult = RepositoryCommitLog;

export type GetRepositoryCommits = (
  params: GetRepositoryCommitsParams
) => Promise<GetRepositoryCommitsResult>;

// gql.tada types the DateTime scalar as unknown; the wire carries ISO 8601 strings.
function dateTime(value: unknown): string {
  if (typeof value !== "string") {
    throw new Error("Expected an ISO 8601 DateTime string");
  }
  return value;
}

function dateTimeOrNull(value: unknown): string | null {
  return value === null || value === undefined ? null : dateTime(value);
}

export const getRepositoryCommits: GetRepositoryCommits = async (params) => {
  const { data, errors } = await getRepositoryCommitsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  const log = data.InfrahubRepositoryCommits;

  return {
    repositoryId: log.repository_id,
    branchName: log.branch_name,
    gitRef: log.git_ref ?? null,
    condition: log.condition,
    importedCommit: log.imported_commit ?? null,
    remoteHead: log.remote_head ?? null,
    pendingCount: log.pending_count ?? null,
    fetchedAt: dateTimeOrNull(log.fetched_at),
    checkedAt: dateTimeOrNull(log.checked_at),
    unavailable: log.unavailable ?? null,
    commits: log.edges.map(
      ({ node }): RepositoryCommit => ({
        id: node.hash,
        __typename: "RepositoryCommit",
        hash: node.hash,
        shortHash: node.short_hash,
        summary: node.summary,
        authorName: node.author_name,
        authoredAt: dateTime(node.authored_at),
        state: node.state,
      })
    ),
  };
};

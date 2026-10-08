import type { RepositoryCommitsResponse } from "@/entities/repository/api/get-repository-commits-from-api";
import type {
  RepositoryCommit,
  RepositoryCommitLog,
} from "@/entities/repository/domain/model/repository";

type RepositoryCommitsWire = RepositoryCommitsResponse["InfrahubRepositoryCommits"];
type RepositoryCommitNodeWire = RepositoryCommitsWire["edges"][number]["node"];

// gql.tada types the DateTime scalar as unknown; the wire carries ISO 8601 strings.
function toDateTime(value: unknown): string {
  if (typeof value !== "string") {
    throw new Error("Expected an ISO 8601 DateTime string");
  }
  return value;
}

function toDateTimeOrNull(value: unknown): string | null {
  return value === null || value === undefined ? null : toDateTime(value);
}

function mapToRepositoryCommit(node: RepositoryCommitNodeWire): RepositoryCommit {
  return {
    hash: node.hash,
    short_hash: node.short_hash,
    summary: node.summary,
    author_name: node.author_name,
    authored_at: toDateTime(node.authored_at),
    state: node.state,
  };
}

export function mapToRepositoryCommitLog(log: RepositoryCommitsWire): RepositoryCommitLog {
  return {
    repository_id: log.repository_id,
    branch_name: log.branch_name,
    git_ref: log.git_ref,
    condition: log.condition,
    imported_commit: log.imported_commit,
    remote_head: log.remote_head,
    pending_count: log.pending_count ?? null,
    fetched_at: toDateTimeOrNull(log.fetched_at),
    checked_at: toDateTimeOrNull(log.checked_at),
    unavailable: log.unavailable && {
      reason: log.unavailable.reason,
      message: log.unavailable.message,
    },
    commits: log.edges.map(({ node }) => mapToRepositoryCommit(node)),
  };
}

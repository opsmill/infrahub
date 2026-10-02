import type {
  RepositoryCommitLog,
  RepositoryCommitStatus,
} from "@/entities/repository/domain/model/repository";

export function getCommitStatusFromLog({
  condition,
  pending_count,
  unavailable,
}: RepositoryCommitLog): RepositoryCommitStatus {
  return { condition, pending_count, unavailable: unavailable && { reason: unavailable.reason } };
}

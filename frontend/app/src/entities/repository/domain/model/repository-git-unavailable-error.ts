import type {
  RepositoryCommitLog,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";

export class RepositoryGitUnavailableError extends Error {
  readonly reason: RepositoryGitUnavailableReason | null;
  readonly log: RepositoryCommitLog;

  constructor(log: RepositoryCommitLog) {
    super(log.unavailable?.message ?? "");
    this.name = "RepositoryGitUnavailableError";
    this.reason = log.unavailable?.reason ?? null;
    this.log = log;
  }
}

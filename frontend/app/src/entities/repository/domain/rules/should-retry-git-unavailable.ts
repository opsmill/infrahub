import { RepositoryGitUnavailableReason } from "@/entities/repository/domain/model/repository";

export function shouldRetryGitUnavailable(reason: RepositoryGitUnavailableReason | null): boolean {
  return reason !== RepositoryGitUnavailableReason.NOT_IMPLEMENTED;
}

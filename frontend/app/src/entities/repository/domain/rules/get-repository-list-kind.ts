import type { BranchRepositoryListKind } from "@/entities/repository/domain/model/branch-repository";
import {
  GENERIC_REPOSITORY_KIND,
  READONLY_REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";

// A branch created with Sync with Git off only tracks read-only repositories.
export function getRepositoryListKind(syncWithGit: boolean): BranchRepositoryListKind {
  return syncWithGit ? GENERIC_REPOSITORY_KIND : READONLY_REPOSITORY_KIND;
}

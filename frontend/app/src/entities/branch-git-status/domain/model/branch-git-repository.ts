import type { BranchRepositoryKind } from "@/entities/repository/domain/model/branch-repository";

export interface BranchGitRepository {
  id: string;
  name: string;
  kind: BranchRepositoryKind;
}

export interface BranchGitRepositoryPage {
  repositories: BranchGitRepository[];
  count: number;
}

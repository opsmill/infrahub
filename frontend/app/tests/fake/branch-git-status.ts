import type { BranchGitRepository } from "@/entities/branch-git-status/domain/model/branch-git-repository";
import type {
  RepositoryBranchStatus,
  RepositoryBranchStatusPage,
} from "@/entities/branch-git-status/domain/model/repository-branch-status";
import type { BranchRepositorySyncStatus } from "@/entities/repository/domain/model/branch-repository";

import {
  READONLY_REPOSITORY_KIND,
  REPOSITORY_KIND,
} from "../../src/entities/repository/domain/model/repository";
import { SYNC_STATUS } from "./branch-repositories";

export const generateBranchGitRepository = (
  overrides: Partial<BranchGitRepository> = {}
): BranchGitRepository => {
  const kind = overrides.kind ?? REPOSITORY_KIND;
  return {
    id: "18a1b2c3-0000-4000-8000-000000000001",
    name: "infrastructure-templates",
    kind,
    isReadOnly: kind === READONLY_REPOSITORY_KIND,
    ...overrides,
  };
};

export const generateRepositoryBranchStatus = (
  overrides: Partial<RepositoryBranchStatus> = {}
): RepositoryBranchStatus => ({
  branchName: "main",
  commit: "9f1c0d4e2b7a6f8c3d5e1a0b4c7d9e2f1a3b5c7d",
  syncStatus: SYNC_STATUS.inSync,
  ...overrides,
});

export const generateRepositoryBranchStatusPage = (
  ...branchNames: string[]
): RepositoryBranchStatusPage => ({
  rows: branchNames.map((branchName) => generateRepositoryBranchStatus({ branchName })),
  count: branchNames.length,
});

export const generateRepositoryBranchStatusWire = (
  branchName: string,
  syncStatus: BranchRepositorySyncStatus | null = SYNC_STATUS.inSync
) => ({
  name: { value: branchName },
  commit: { value: "9f1c0d4e2b7a6f8c3d5e1a0b4c7d9e2f1a3b5c7d" },
  sync_status: syncStatus,
});

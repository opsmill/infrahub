import type { BranchGitRepository } from "@/entities/branch-git-status/domain/model/branch-git-repository";
import type { BranchGitSyncStatus } from "@/entities/branch-git-status/domain/model/branch-git-status";
import type {
  RepositoryBranchGitStatus,
  RepositoryBranchGitStatusPage,
} from "@/entities/branch-git-status/domain/model/repository-branch-git-status";

import { REPOSITORY_KIND } from "../../src/entities/repository/domain/model/repository";
import { SYNC_STATUS } from "./branch-repositories";

const COMMIT = "9f1c0d4e2b7a6f8c3d5e1a0b4c7d9e2f1a3b5c7d";

export const generateBranchGitRepository = (
  overrides: Partial<BranchGitRepository> = {}
): BranchGitRepository => ({
  id: "18a1b2c3-0000-4000-8000-000000000001",
  name: "infrastructure-templates",
  kind: REPOSITORY_KIND,
  ...overrides,
});

export const generateRepositoryBranchGitStatus = (
  overrides: Partial<RepositoryBranchGitStatus> = {}
): RepositoryBranchGitStatus => ({
  branchName: "main",
  commit: COMMIT,
  syncStatus: SYNC_STATUS.inSync,
  ...overrides,
});

export const generateRepositoryBranchGitStatusPage = ({
  branchNames = ["main"],
  ...overrides
}: Partial<RepositoryBranchGitStatusPage> & {
  branchNames?: string[];
} = {}): RepositoryBranchGitStatusPage => ({
  rows: branchNames.map((branchName) => generateRepositoryBranchGitStatus({ branchName })),
  count: branchNames.length,
  ...overrides,
});

export const generateRepositoryBranchGitStatusWire = ({
  branchName = "main",
  syncStatus = SYNC_STATUS.inSync,
}: {
  branchName?: string;
  syncStatus?: BranchGitSyncStatus | null;
} = {}) => ({
  name: { value: branchName },
  commit: { value: COMMIT },
  sync_status: syncStatus,
});

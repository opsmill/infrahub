import type {
  BranchRepository,
  BranchRepositoryHealth,
  BranchRepositoryPage,
  BranchRepositorySyncStatus,
} from "@/entities/repository/domain/model/branch-repository";

import {
  READONLY_REPOSITORY_KIND,
  REPOSITORY_KIND,
} from "../../src/entities/repository/domain/model/repository";

// Label, colour and description mirror the CoreGenericRepository.sync_status dropdown choices.
export const SYNC_STATUS = {
  inSync: {
    value: "in-sync",
    label: "In Sync",
    color: "#60a5fa",
    description: "The repository is syncing correctly",
  },
  importError: {
    value: "error-import",
    label: "Import Error",
    color: "#f87171",
    description: "Repository import error observed",
  },
  syncing: {
    value: "syncing",
    label: "Syncing",
    color: "#a855f7",
    description: "A sync job is currently running against the repository.",
  },
  unknown: {
    value: "unknown",
    label: "Unknown",
    color: "#9ca3af",
    description:
      "Status of the repository is unknown and mostlikely because it hasn't been synced yet",
  },
} satisfies Record<string, BranchRepositorySyncStatus>;

export const OPERATIONAL_STATUS = {
  online: { value: "online", label: "Online" },
  errorCred: { value: "error-cred", label: "Credential Error" },
  errorConnection: { value: "error-connection", label: "Connectivity Error" },
  error: { value: "error", label: "Error" },
  unknown: { value: "unknown", label: "Unknown" },
};

export const generateBranchRepository = (
  overrides: Partial<BranchRepository> = {}
): BranchRepository => {
  const kind = overrides.kind ?? REPOSITORY_KIND;
  return {
    id: "18a1b2c3-0000-4000-8000-000000000001",
    kind,
    name: "infrastructure-templates",
    isReadOnly: kind === READONLY_REPOSITORY_KIND,
    commit: "8f3c2a1",
    syncStatus: SYNC_STATUS.inSync,
    operationalStatus: OPERATIONAL_STATUS.online,
    ...overrides,
  };
};

export const generateBranchRepositoryHealth = (
  overrides: Partial<BranchRepositoryHealth> = {}
): BranchRepositoryHealth => ({
  importErrors: [],
  unreachable: [],
  syncingCount: 0,
  ...overrides,
});

// What the server's filtered lists would return for these repositories.
export const toBranchRepositoryHealth = (
  repositories: BranchRepository[]
): BranchRepositoryHealth => ({
  importErrors: repositories.filter(
    ({ syncStatus }) => syncStatus.value === SYNC_STATUS.importError.value
  ),
  unreachable: repositories.filter(({ operationalStatus }) =>
    ["error-cred", "error-connection", "error"].includes(operationalStatus.value ?? "")
  ),
  syncingCount: repositories.filter(({ syncStatus }) => syncStatus.value === "syncing").length,
});

// One page of these repositories, as the server would slice it.
export const toBranchRepositoryPage = (
  repositories: BranchRepository[],
  { offset = 0, limit = 10 }: { offset?: number; limit?: number } = {}
): BranchRepositoryPage => ({
  repositories: repositories.slice(offset, offset + limit),
  count: repositories.length,
});

const BASE_REPOSITORIES: BranchRepository[] = [
  generateBranchRepository({
    id: "repo-1",
    name: "network-automation-generators-emea-datacenter-fabric-templates",
    commit: "7fa2e51",
  }),
  generateBranchRepository({ id: "repo-2", name: "infrastructure-templates", commit: "8f3c2a1" }),
  generateBranchRepository({ id: "repo-3", name: "network-services", commit: "61ba9c3" }),
  generateBranchRepository({
    id: "repo-4",
    kind: READONLY_REPOSITORY_KIND,
    name: "vendor-golden-configs",
    commit: "77aa01b",
  }),
];

const fillerRepository = (n: number) =>
  generateBranchRepository({
    id: `filler-${n}`,
    name: `site-config-${String(n).padStart(2, "0")}`,
    commit: (0x1_a2_b3_c4 + n * 7919).toString(16).slice(0, 7),
  });

const buildRepositories = (total: number): BranchRepository[] => {
  const repositories = BASE_REPOSITORIES.slice(0, total);
  for (let n = 1; repositories.length < total; n++) repositories.push(fillerRepository(n));
  return repositories;
};

const withImportError = (repository: BranchRepository): BranchRepository => ({
  ...repository,
  syncStatus: SYNC_STATUS.importError,
});

const updateAt = (
  repositories: BranchRepository[],
  positions: number[],
  update: (repository: BranchRepository) => BranchRepository
) =>
  repositories.map((repository, index) =>
    positions.includes(index + 1) ? update(repository) : repository
  );

export const MANY_ERRORS_IMPORT_ERROR_POSITIONS = [2, 3, 7, 12, 18];

export type BranchRepositoriesScenario =
  | "incident"
  | "import-error"
  | "unreachable"
  | "many-errors"
  | "all-clear"
  | "no-repos"
  | "exactly-10"
  | "eleven";

export const buildBranchRepositoriesScenario = (
  scenario: BranchRepositoriesScenario
): BranchRepository[] => {
  switch (scenario) {
    case "incident":
    case "import-error":
      return updateAt(buildRepositories(4), [2], withImportError);
    case "unreachable":
      return updateAt(buildRepositories(4), [3], (repository) => ({
        ...repository,
        operationalStatus: OPERATIONAL_STATUS.errorCred,
      }));
    case "many-errors":
      return updateAt(buildRepositories(40), MANY_ERRORS_IMPORT_ERROR_POSITIONS, withImportError);
    case "all-clear":
      return buildRepositories(4);
    case "no-repos":
      return [];
    case "exactly-10":
      return buildRepositories(10);
    case "eleven":
      return buildRepositories(11);
  }
};

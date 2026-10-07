import type {
  RepositoryBranchStatusWireNode,
  RepositoryBranchStatusWirePage,
} from "@/entities/repository/domain/model/repository-branch-status";

import { generateDropdown } from "./dropdown";

export type RepositoryBranchStatusWire = Required<RepositoryBranchStatusWireNode>;

export type RepositoryBranchStatusPageWire = Omit<RepositoryBranchStatusWirePage, "edges"> & {
  edges: Array<{ node: RepositoryBranchStatusWire }>;
};

export const generateRepositoryBranchStatus = (
  overrides?: Partial<RepositoryBranchStatusWire>
): RepositoryBranchStatusWire => ({
  name: { value: "main" },
  is_default: { value: true },
  commit: { value: "9f1c0d4e2b7a6f8c3d5e1a0b4c7d9e2f1a3b5c7d" },
  sync_status: generateDropdown(),
  ref: null,
  ...overrides,
});

export const generateReadOnlyRepositoryBranchStatus = (
  overrides?: Partial<RepositoryBranchStatusWire>
): RepositoryBranchStatusWire =>
  generateRepositoryBranchStatus({ ref: { value: "refs/tags/v1.4.2" }, ...overrides });

export const generateSparseRepositoryBranchStatus = (
  overrides?: Partial<RepositoryBranchStatusWire>
): RepositoryBranchStatusWire =>
  generateRepositoryBranchStatus({
    is_default: null,
    commit: null,
    sync_status: null,
    ref: null,
    ...overrides,
  });

export const generateRepositoryBranchStatusPage = ({
  rows,
  count,
}: {
  rows: RepositoryBranchStatusWire[];
  count?: number;
}): RepositoryBranchStatusPageWire => ({
  count: count ?? rows.length,
  edges: rows.map((node) => ({ node })),
});

const BRANCH_NAMES_BEFORE = ["main", "feature-auth", "staging"] as const;

const branchRow = (name: string) =>
  generateRepositoryBranchStatus({
    name: { value: name },
    is_default: { value: name === "main" },
  });

export const generateRepositoryBranchStatusPayloadBefore = (options?: {
  count?: number;
}): RepositoryBranchStatusPageWire =>
  generateRepositoryBranchStatusPage({
    rows: BRANCH_NAMES_BEFORE.map((name) => branchRow(name)),
    count: options?.count,
  });

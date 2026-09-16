import type {
  NonRequiredBooleanValueField,
  RequiredStringValueField,
  TextAttribute,
} from "@/shared/api/graphql/generated/types";

import { type DropdownSelection, generateDropdown } from "./dropdown";

export type RepositoryBranchStatusWire = {
  name: Pick<RequiredStringValueField, "value">;
  is_default: Pick<NonRequiredBooleanValueField, "value"> | null;
  commit: Pick<TextAttribute, "value"> | null;
  sync_status: DropdownSelection | null;
  ref: Pick<TextAttribute, "value"> | null;
};

export type RepositoryBranchStatusPageWire = {
  count: number;
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

export const BRANCH_NAMES_BEFORE = ["main", "feature-auth", "staging"] as const;
export const BRANCH_NAMES_AFTER = ["release-2-0", "hotfix-tls", "spike-graph"] as const;

const branchRow = (name: string) =>
  generateRepositoryBranchStatus({
    name: { value: name },
    is_default: { value: name === "main" },
  });

// No branch appears in both payloads, so a rendered row set can only belong to one of them.
export const generateRepositoryBranchStatusPayloadBefore = (options?: {
  count?: number;
}): RepositoryBranchStatusPageWire =>
  generateRepositoryBranchStatusPage({
    rows: BRANCH_NAMES_BEFORE.map((name) => branchRow(name)),
    count: options?.count,
  });

export const generateRepositoryBranchStatusPayloadAfter = (options?: {
  count?: number;
}): RepositoryBranchStatusPageWire =>
  generateRepositoryBranchStatusPage({
    rows: BRANCH_NAMES_AFTER.map((name) => branchRow(name)),
    count: options?.count,
  });

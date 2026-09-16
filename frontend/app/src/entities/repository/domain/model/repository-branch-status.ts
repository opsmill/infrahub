import type {
  BranchStatus,
  Dropdown,
  NonRequiredBooleanValueField,
  NonRequiredStringValueField,
  RequiredStringValueField,
  StatusField,
  TextAttribute,
} from "@/shared/api/graphql/generated/types";

export type RepositoryBranchStatusDropdown = Pick<
  Dropdown,
  "value" | "label" | "color" | "description"
>;

export interface RepositoryBranchStatusWireNode {
  name: Pick<RequiredStringValueField, "value">;
  status: Pick<StatusField, "value">;
  is_default?: Pick<NonRequiredBooleanValueField, "value"> | null;
  sync_with_git?: Pick<NonRequiredBooleanValueField, "value"> | null;
  branched_from?: Pick<NonRequiredStringValueField, "value"> | null;
  commit?: Pick<TextAttribute, "value"> | null;
  sync_status?: RepositoryBranchStatusDropdown | null;
  internal_status?: RepositoryBranchStatusDropdown | null;
  ref?: Pick<TextAttribute, "value"> | null;
}

export interface RepositoryBranchStatusWirePage {
  count: number;
  edges: Array<{ node: RepositoryBranchStatusWireNode }>;
}

export const REPOSITORY_BRANCH_STATUS_TYPENAME = "InfrahubRepositoryBranchStatus";

export interface RepositoryBranchStatusRow {
  id: string;
  __typename: string;
  name: string;
  status: BranchStatus;
  isDefault: boolean;
  syncWithGit: boolean;
  branchedFrom: string | null;
  commit: string | null;
  syncStatus: RepositoryBranchStatusDropdown | null;
  internalStatus: RepositoryBranchStatusDropdown | null;
  ref: string | null;
}

export interface RepositoryBranchStatusPage {
  rows: RepositoryBranchStatusRow[];
  count: number;
}

export type RepositoryBranchStatusErrorCode = "PERMISSION_DENIED" | "UNKNOWN";

export class RepositoryBranchStatusError extends Error {
  readonly code: RepositoryBranchStatusErrorCode;

  constructor(code: RepositoryBranchStatusErrorCode, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "RepositoryBranchStatusError";
    this.code = code;
  }
}

// A dropdown with no value is not a selection, so it collapses to null rather than travelling on as
// a half-populated object.
function toDropdown(
  dropdown: RepositoryBranchStatusDropdown | null | undefined
): RepositoryBranchStatusDropdown | null {
  if (!dropdown || dropdown.value === null || dropdown.value === undefined) return null;
  return dropdown;
}

export function mapRepositoryBranchStatusRow(
  node: RepositoryBranchStatusWireNode
): RepositoryBranchStatusRow {
  return {
    // The contract guarantees one row per branch, so the branch name is a sound row key.
    id: node.name.value,
    __typename: REPOSITORY_BRANCH_STATUS_TYPENAME,
    name: node.name.value,
    status: node.status.value,
    isDefault: node.is_default?.value ?? false,
    syncWithGit: node.sync_with_git?.value ?? false,
    branchedFrom: node.branched_from?.value ?? null,
    commit: node.commit?.value ?? null,
    syncStatus: toDropdown(node.sync_status),
    internalStatus: toDropdown(node.internal_status),
    ref: node.ref?.value ?? null,
  };
}

export function mapRepositoryBranchStatusPage(
  page: RepositoryBranchStatusWirePage
): RepositoryBranchStatusPage {
  return {
    rows: page.edges.map((edge) => mapRepositoryBranchStatusRow(edge.node)),
    count: page.count,
  };
}

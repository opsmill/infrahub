export const BRANCH_STATUS = {
  OPEN: "OPEN",
  NEED_REBASE: "NEED_REBASE",
  NEED_UPGRADE_REBASE: "NEED_UPGRADE_REBASE",
  DELETING: "DELETING",
} as const;

export type BranchStatus = (typeof BRANCH_STATUS)[keyof typeof BRANCH_STATUS];

import { BRANCH_STATUS, type BranchStatus } from "@/entities/branches/constants";
import type { PermissionDecision } from "@/entities/permission/types";

/**
 * Result of computing action availability and tooltip message.
 */
export interface ActionAvailability {
  /** Whether the action is allowed */
  isAllowed: boolean;
  /** Tooltip message to display (undefined if action is allowed) */
  tooltipMessage: string | undefined;
}

/**
 * Centralized logic for determining if an action is allowed and what tooltip to show.
 * This is the single source of truth for action availability logic.
 *
 * Priority order:
 * 1. Branch merged → disabled with "Cannot edit objects on a merged branch"
 * 2. Permission denied → disabled with permission message
 * 3. Otherwise → allowed with no tooltip
 *
 * @param branchStatus - Current branch status
 * @param permissionDecision - Permission decision (isAllowed + message)
 * @returns Object with isAllowed flag and tooltipMessage
 */
export function getActionAvailability(
  branchStatus: BranchStatus,
  permissionDecision: PermissionDecision
): ActionAvailability {
  // Branch merged takes priority
  if (branchStatus === BRANCH_STATUS.MERGED) {
    return {
      isAllowed: false,
      tooltipMessage: "Cannot edit objects on a merged branch",
    };
  }

  // Permission check
  if (!permissionDecision.isAllowed) {
    return {
      isAllowed: false,
      tooltipMessage: permissionDecision.message,
    };
  }

  // Action is allowed
  return {
    isAllowed: true,
    tooltipMessage: undefined,
  };
}

/**
 * @deprecated Use getActionAvailability instead for centralized logic
 */
export function getActionTooltip(
  branchStatus: BranchStatus,
  permissionMessage: string | undefined
): string | undefined {
  if (branchStatus === BRANCH_STATUS.MERGED) {
    return "Cannot edit objects on a merged branch";
  }

  return permissionMessage;
}

/**
 * @deprecated Use getActionAvailability instead for centralized logic
 */
export function isActionAllowed(branchStatus: BranchStatus, isPermissionAllowed: boolean): boolean {
  if (branchStatus === BRANCH_STATUS.MERGED) {
    return false;
  }

  return isPermissionAllowed;
}

import {
  BRANCH_DELETED_EVENT,
  BRANCH_MERGED_EVENT,
} from "@/entities/branches/domain/model/branch-events";

export const PROPOSED_CHANGE_MERGED = "infrahub.proposed_change.merged";
export const PROPOSED_CHANGE_REVIEW_REQUESTED = "infrahub.proposed_change.review_requested";
export const PROPOSED_CHANGE_APPROVED = "infrahub.proposed_change.approved";
export const PROPOSED_CHANGE_APPROVAL_REVOKED = "infrahub.proposed_change.approval_revoked";
export const PROPOSED_CHANGE_REJECTED = "infrahub.proposed_change.rejected";
export const PROPOSED_CHANGE_REJECTION_REVOKED = "infrahub.proposed_change.rejection_revoked";
export const PROPOSED_CHANGE_COMMENT = "infrahub.proposed_change.comment";
export const PROPOSED_CHANGE_THREAD = "infrahub.proposed_change_thread.created";
export const PROPOSED_CHANGE_APPROVALS_REVOKED = "infrahub.proposed_change.approvals_revoked";

export const PROPOSED_CHANGE_EVENTS = [
  PROPOSED_CHANGE_MERGED,
  PROPOSED_CHANGE_REVIEW_REQUESTED,
  PROPOSED_CHANGE_APPROVED,
  PROPOSED_CHANGE_REJECTED,
  PROPOSED_CHANGE_APPROVAL_REVOKED,
  PROPOSED_CHANGE_REJECTION_REVOKED,
  PROPOSED_CHANGE_COMMENT,
  PROPOSED_CHANGE_THREAD,
  PROPOSED_CHANGE_APPROVALS_REVOKED,
  BRANCH_MERGED_EVENT,
  BRANCH_DELETED_EVENT,
];

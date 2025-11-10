import type { StateItem } from "@/entities/proposed-changes/ui/action-button/types";

export const APPROVE_DECISION = "APPROVE";
export const CANCEL_APPROVE_DECISION = "CANCEL_APPROVE";
export const REJECT_DECISION = "REJECT";
export const CANCEL_REJECT_DECISION = "CANCEL_REJECT";

export const OPEN_STATE = "open";
export const MERGE_STATE = "merged";
export const MERGING_STATE = "merging";
export const CLOSE_STATE = "closed";
export const DRAFT_STATE = "draft";
export const CANCEL_STATE = "canceled";
export const PROPOSED_CHANGE_OBJECT = "CoreProposedChange";

export const STATE_VALUES_FILTER = "state__values";

export const PROPOSED_CHANGE_STATES = {
  opened: [OPEN_STATE, MERGING_STATE],
  closed: [CLOSE_STATE, MERGE_STATE, CANCEL_STATE],
};

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
];

export const pcStatesList: Record<string, StateItem> = {
  open: {
    value: "open",
    name: "Open",
    message: "Open",
  },
  draft: {
    value: "draft",
    name: "Draft",
    message: "Open a draft",
  },
};

export const APPROVE_DECISION = "APPROVE";
export const CANCEL_APPROVE_DECISION = "CANCEL_APPROVE";
export const REJECT_DECISION = "REJECT";
export const CANCEL_REJECT_DECISION = "CANCEL_REJECT";

export const OPEN_STATE = "open";
export const MERGE_STATE = "merged";
export const MERGING_STATE = "merging";
export const CLOSE_STATE = "closed";
export const DRAFT_STATE = "draft";
export const PROPOSED_CHANGE_OBJECT = "CoreProposedChange";

export const PROPOSED_CHANGE_STATES = {
  opened: [OPEN_STATE, MERGING_STATE],
  closed: [CLOSE_STATE, MERGE_STATE, "canceled"],
};

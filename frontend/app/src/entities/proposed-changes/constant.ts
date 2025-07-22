export const APPROVE_DECISION = "APPROVE";
export const CANCEL_APPROVE_DECISION = "CENCEL_APPROVE";
export const REJECT_DECISION = "REJECT";
export const CANCEL_REJECT_DECISION = "CENCEL_REJECT";

export const MERGE_STATE = "MERGE";
export const OPEN_STATE = "OPEN";
export const CLOSE_STATE = "CLOSE";
export const PROPOSED_CHANGE_OBJECT = "CoreProposedChange";

export const PROPOSED_CHANGE_STATES = {
  opened: ["open", "merging"],
  closed: ["closed", "merged", "canceled"],
};

export const QSP_STATE_CLOSE_VALUE = "closed";

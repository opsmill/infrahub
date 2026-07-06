/** Lifecycle states of a proposed change. */
export const OPEN_STATE = "open";
export const MERGE_STATE = "merged";
export const MERGING_STATE = "merging";
export const CLOSE_STATE = "closed";
export const DRAFT_STATE = "draft";
export const CANCEL_STATE = "canceled";

/** States in which a proposed change can still be edited. */
export const PROPOSED_CHANGES_EDITABLE_STATE = ["open", "closed"];

/** The states grouped into their coarse open/closed buckets. */
export const PROPOSED_CHANGE_STATES = {
  opened: [OPEN_STATE, MERGING_STATE],
  closed: [CLOSE_STATE, MERGE_STATE, CANCEL_STATE],
};

/** GraphQL filter key for querying by state. */
export const STATE_VALUES_FILTER = "state__values";

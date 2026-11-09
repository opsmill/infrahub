import {
  DRAFT_STATE,
  OPEN_STATE,
} from "@/entities/proposed-changes/domain/model/proposed-change-state";

/** A selectable state option, with its display name and helper message. */
export type StateItem = { value: string; name: string; message: string };

/** The states a user can pick when creating a proposed change (UI selection copy). */
export const pcStatesList: Record<string, StateItem> = {
  [OPEN_STATE]: {
    value: OPEN_STATE,
    name: "Open",
    message: "Open",
  },
  [DRAFT_STATE]: {
    value: DRAFT_STATE,
    name: "Draft",
    message: "Open a draft",
  },
};

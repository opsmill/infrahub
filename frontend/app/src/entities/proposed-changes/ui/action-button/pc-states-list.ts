/** A selectable state option, with its display name and helper message. */
export type StateItem = { value: string; name: string; message: string };

/** The states a user can pick when creating a proposed change (UI selection copy). */
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

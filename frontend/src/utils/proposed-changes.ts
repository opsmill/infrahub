import { BADGE_TYPES } from "../components/display/badge";

export const getProposedChangesStateBadgeType = (state: string): BADGE_TYPES | undefined => {
  switch (state) {
    case "open": {
      return BADGE_TYPES.VALIDATE;
    }
    case "closed": {
      return BADGE_TYPES.CANCEL;
    }
    case "merged": {
      return BADGE_TYPES.WARNING;
    }
    case "canceled": {
      return BADGE_TYPES.DISABLED;
    }
    default: {
      return undefined;
    }
  }
};

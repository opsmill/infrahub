import { BadgeProps } from "@/components/ui/badge";

export const getProposedChangesStateBadgeType = (
  state: string
): BadgeProps["variant"] | undefined => {
  switch (state) {
    case "open": {
      return "green";
    }
    case "closed": {
      return "red";
    }
    case "merged": {
      return "yellow";
    }
    case "canceled": {
      return "gray";
    }
    default: {
      return undefined;
    }
  }
};

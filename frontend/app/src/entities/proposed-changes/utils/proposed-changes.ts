import type { BadgeProps } from "@/shared/components/ui/badge";

export const getProposedChangesStateBadgeType = (
  state: string
): BadgeProps["variant"] | undefined => {
  switch (state) {
    case "open": {
      return "green-outline";
    }
    case "closed": {
      return "red-outline";
    }
    case "merged": {
      return "yellow-outline";
    }
    case "canceled": {
      return "gray-outline";
    }
    default: {
      return;
    }
  }
};

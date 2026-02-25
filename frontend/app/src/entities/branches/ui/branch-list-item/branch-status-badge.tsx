import { Badge, type BadgeProps } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import { BRANCH_STATUS, type BranchStatus } from "@/entities/branches/constants";

const pillStyle = "rounded-full font-normal";

interface BranchStatusBadgeProps extends BadgeProps {
  status: BranchStatus;
  /** Whether to show the badge for OPEN status. Default: false */
  showOpen?: boolean;
}

export function BranchStatusBadge({
  status,
  className,
  showOpen = false,
  ...props
}: BranchStatusBadgeProps) {
  switch (status) {
    case BRANCH_STATUS.OPEN: {
      if (!showOpen) return null;
      return (
        <Badge className={classNames(pillStyle, className)} variant="green" {...props}>
          Open
        </Badge>
      );
    }
    case BRANCH_STATUS.NEED_REBASE: {
      return (
        <Badge className={classNames(pillStyle, className)} variant="yellow" {...props}>
          Rebase needed
        </Badge>
      );
    }
    case BRANCH_STATUS.NEED_UPGRADE_REBASE: {
      return (
        <Badge className={classNames(pillStyle, className)} variant="yellow" {...props}>
          Rebase needed (upgrade)
        </Badge>
      );
    }
    case BRANCH_STATUS.DELETING: {
      return (
        <Badge className={classNames(pillStyle, className)} variant="red" {...props}>
          Deleting
        </Badge>
      );
    }
    case BRANCH_STATUS.MERGED: {
      return (
        <Badge className={classNames(pillStyle, className)} variant="purple" {...props}>
          Merged
        </Badge>
      );
    }
    default: {
      return null;
    }
  }
}

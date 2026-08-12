import { BranchStatus } from "@/shared/api/graphql/generated/types";
import { Badge, type BadgeProps } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

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
    case BranchStatus.OPEN: {
      if (!showOpen) return null;
      return (
        <Badge className={classNames(pillStyle, className)} variant="green" {...props}>
          Open
        </Badge>
      );
    }
    case BranchStatus.NEED_REBASE: {
      return (
        <Badge className={classNames(pillStyle, className)} variant="yellow" {...props}>
          Rebase needed
        </Badge>
      );
    }
    case BranchStatus.NEED_UPGRADE_REBASE: {
      return (
        <Badge className={classNames(pillStyle, className)} variant="yellow" {...props}>
          Rebase needed (upgrade)
        </Badge>
      );
    }
    case BranchStatus.DELETING: {
      return (
        <Badge className={classNames(pillStyle, className)} variant="red" {...props}>
          Deleting
        </Badge>
      );
    }
    case BranchStatus.MERGED: {
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

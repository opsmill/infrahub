import { AlertTriangleIcon, LoaderIcon } from "lucide-react";

import { Badge, type BadgeProps } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import { BRANCH_STATUS, type BranchStatus } from "@/entities/branches/constants";

const pillStyle = "gap-1 rounded-full font-normal";

interface BranchStatusBadgeProps extends BadgeProps {
  status: BranchStatus;
}

export function BranchStatusBadge({ status, className, ...props }: BranchStatusBadgeProps) {
  switch (status) {
    case BRANCH_STATUS.OPEN: {
      return null;
    }
    case BRANCH_STATUS.NEED_REBASE: {
      return (
        <Badge className={classNames(pillStyle, className)} variant="yellow" {...props}>
          <AlertTriangleIcon className="size-3" /> Rebase needed
        </Badge>
      );
    }
    case BRANCH_STATUS.NEED_UPGRADE_REBASE: {
      return (
        <Badge className={classNames(pillStyle, className)} variant="yellow" {...props}>
          <AlertTriangleIcon className="size-3" /> Rebase needed (upgrade)
        </Badge>
      );
    }
    case BRANCH_STATUS.DELETING: {
      return (
        <Badge className={classNames(pillStyle, className)} variant="red" {...props}>
          <LoaderIcon className="size-3 animate-spin" /> Deleting
        </Badge>
      );
    }
    default: {
      return null;
    }
  }
}

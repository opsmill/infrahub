import { AlertTriangleIcon, LoaderIcon } from "lucide-react";

import { Badge, type BadgeProps } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import { BRANCH_STATUS_OPEN } from "@/entities/branches/constants";

const pillStyle = "gap-1 rounded-full font-normal";

interface BranchStatusBadgeProps extends BadgeProps {
  status: string;
}

export function BranchStatusBadge({ status, className, ...props }: BranchStatusBadgeProps) {
  switch (status) {
    case BRANCH_STATUS_OPEN: {
      return null;
    }
    case "NEED_REBASE": {
      return (
        <Badge className={classNames(pillStyle, className)} variant="yellow" {...props}>
          <AlertTriangleIcon className="size-3" /> Rebase needed
        </Badge>
      );
    }
    case "NEED_UPGRADE_REBASE": {
      return (
        <Badge className={classNames(pillStyle, className)} variant="yellow" {...props}>
          <AlertTriangleIcon className="size-3" /> Rebase needed (upgrade)
        </Badge>
      );
    }
    case "DELETING": {
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

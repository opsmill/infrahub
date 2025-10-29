import { AlertTriangleIcon, LoaderIcon } from "lucide-react";

import type { BranchStatus } from "@/shared/api/graphql/generated/graphql";
import { Badge, type BadgeProps } from "@/shared/components/ui/badge";
import { classNames, warnUnexpectedType } from "@/shared/utils/common";

const pillStyle = "gap-1 rounded-full font-normal";

interface BranchStatusBadgeProps extends BadgeProps {
  status: BranchStatus;
}

export function BranchStatusBadge({ status, className, ...props }: BranchStatusBadgeProps) {
  switch (status) {
    case "OPEN": {
      return (
        <Badge className={classNames(pillStyle, className)} variant="green" {...props}>
          open
        </Badge>
      );
    }
    case "NEED_REBASE": {
      return (
        <Badge className={classNames(pillStyle, className)} variant="yellow" {...props}>
          <AlertTriangleIcon className="size-3" /> Rebase needed
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
      warnUnexpectedType(status);
      return null;
    }
  }
}

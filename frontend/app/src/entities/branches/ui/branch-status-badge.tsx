import { AlertTriangleIcon, LoaderIcon } from "lucide-react";

import type { BranchStatus } from "@/shared/api/graphql/generated/graphql";
import { Badge } from "@/shared/components/ui/badge";
import { warnUnexpectedType } from "@/shared/utils/common";

interface BranchStatusBadgeProps {
  status: BranchStatus;
}

export function BranchStatusBadge({ status }: BranchStatusBadgeProps) {
  switch (status) {
    case "OPEN": {
      return null;
    }
    case "NEED_REBASE": {
      return (
        <Badge className="gap-1 rounded-full font-normal" variant="yellow">
          <AlertTriangleIcon className="size-3" /> Rebase needed
        </Badge>
      );
    }
    case "DELETING": {
      return (
        <Badge className="gap-1 rounded-full font-normal" variant="red">
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

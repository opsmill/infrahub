import { BoxIcon } from "lucide-react";

import { Badge } from "@/shared/components/ui/badge";

export function BranchSchemaChangesBadge() {
  return (
    <Badge className="gap-1 rounded-full font-normal text-gray-600">
      <BoxIcon className="size-3" /> schema updated
    </Badge>
  );
}

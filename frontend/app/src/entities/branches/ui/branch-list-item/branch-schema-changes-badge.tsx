import { Badge, type BadgeProps } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

export function BranchSchemaChangesBadge({ className, ...props }: BadgeProps) {
  return (
    <Badge className={classNames("rounded-full font-normal text-gray-600", className)} {...props}>
      schema updated
    </Badge>
  );
}

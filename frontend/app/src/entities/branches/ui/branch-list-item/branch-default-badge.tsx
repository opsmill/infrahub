import { Badge, type BadgeProps } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

export function BranchDefaultBadge({ className, ...props }: BadgeProps) {
  return (
    <Badge className={classNames("rounded-full font-normal text-gray-700", className)} {...props}>
      default
    </Badge>
  );
}

import type { BadgeProps } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

export function BranchDefaultBadge({ className, ...props }: BadgeProps) {
  return (
    <span
      className={classNames(
        "rounded-full border border-border-strong bg-transparent px-1.5 py-0.5 text-stone-600 text-xs",
        className
      )}
      {...props}
    >
      default
    </span>
  );
}

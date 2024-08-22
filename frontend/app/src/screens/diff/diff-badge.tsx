import { Badge, BadgeProps } from "@/components/ui/badge";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";

export interface DiffBadgeProps extends BadgeProps {
  hasConflicts?: boolean;
}

export type BadgeType =
  | typeof BadgeAdded
  | typeof BadgeRemoved
  | typeof BadgeUpdated
  | typeof BadgeUnchanged
  | typeof BadgeConflict;

export const BadgeUnchanged = ({
  icon,
  className,
  children,
  hasConflicts = false,
  ...props
}: DiffBadgeProps & { icon?: string }) => {
  return (
    <Badge
      className={classNames(
        "p-1 text-base rounded-full",
        (children || children === 0) && "inline-flex gap-1 px-2",
        hasConflicts && "border-none p-0 pl-1",
        className
      )}
      {...props}>
      <Icon icon={icon ?? "mdi:check"} className="text-xs" />
      {(children || children === 0) && <span className="font-medium text-xs">{children}</span>}
      {hasConflicts && <BadgeConflict />}
    </Badge>
  );
};

export const BadgeAdded = ({ ...props }: DiffBadgeProps) => {
  return (
    <BadgeUnchanged
      {...props}
      icon="mdi:plus-circle-outline"
      className="bg-green-200 text-green-800"
    />
  );
};

export const BadgeRemoved = ({ ...props }: DiffBadgeProps) => {
  return (
    <BadgeUnchanged
      {...props}
      icon="mdi:minus-circle-outline"
      className="bg-red-200 text-red-800"
    />
  );
};

export const BadgeConflict = ({ ...props }: DiffBadgeProps) => {
  return (
    <BadgeUnchanged
      {...props}
      icon="mdi:warning-outline"
      className="bg-yellow-200 text-yellow-800"
    />
  );
};

export const BadgeUpdated = ({ ...props }: DiffBadgeProps) => {
  return (
    <BadgeUnchanged {...props} icon="mdi:circle-arrows" className="bg-blue-200 text-blue-800" />
  );
};

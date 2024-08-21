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
      <Icon icon={icon ?? "mdi:check"} />
      {(children || children === 0) && <span className="font-medium text-xs">{children}</span>}
      {hasConflicts && <BadgeConflict />}
    </Badge>
  );
};

export const BadgeAdded = ({ ...props }: DiffBadgeProps) => {
  return <BadgeUnchanged {...props} icon="mdi:plus-circle-outline" variant="green" />;
};

export const BadgeRemoved = ({ ...props }: DiffBadgeProps) => {
  return <BadgeUnchanged {...props} icon="mdi:minus-circle-outline" variant="red" />;
};

export const BadgeConflict = ({ ...props }: DiffBadgeProps) => {
  return <BadgeUnchanged {...props} icon="mdi:warning-outline" variant="yellow" />;
};

export const BadgeUpdated = ({ ...props }: DiffBadgeProps) => {
  return <BadgeUnchanged {...props} icon="mdi:circle-arrows" variant="blue" />;
};

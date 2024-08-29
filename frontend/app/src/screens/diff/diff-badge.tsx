import { Badge, BadgeProps } from "@/components/ui/badge";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";

export interface DiffBadgeProps extends BadgeProps {
  hasConflicts?: boolean;
}

type CloseBadgeProps = {
  className?: string;
};

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
        (children || children === 0) && "gap-1 px-2",
        hasConflicts && "border-none p-0 pl-1 gap-1",
        className
      )}
      {...props}>
      <Icon icon={icon ?? "mdi:check"} className="text-xs" />
      {(children || children === 0) && <span className="font-medium text-xs">{children}</span>}
      {hasConflicts && <BadgeConflict />}
    </Badge>
  );
};

export const BadgeAdded = ({ className, ...props }: DiffBadgeProps) => {
  return (
    <BadgeUnchanged
      {...props}
      icon="mdi:plus-circle-outline"
      className={classNames("bg-green-200 text-green-800", className)}
    />
  );
};

export const CloseBadgeAdded = ({ className }: CloseBadgeProps) => {
  return (
    <div
      className={classNames(
        "flex justify-center items-center absolute border-2 border-white -top-2 -right-2 bg-green-200 text-green-800 rounded-full",
        className
      )}>
      <Icon icon="mdi:close" size={1} />
    </div>
  );
};

export const BadgeRemoved = ({ className, ...props }: DiffBadgeProps) => {
  return (
    <BadgeUnchanged
      {...props}
      icon="mdi:minus-circle-outline"
      className={classNames("bg-red-200 text-red-800", className)}
    />
  );
};

export const CloseBadgeRemoved = ({ className }: CloseBadgeProps) => {
  return (
    <div
      className={classNames(
        "flex justify-center items-center absolute border-2 border-white -top-2 -right-2 bg-red-200 text-red-800 rounded-full",
        className
      )}>
      <Icon icon="mdi:close" size={1} />
    </div>
  );
};

export const BadgeConflict = ({ className, ...props }: DiffBadgeProps) => {
  return (
    <BadgeUnchanged
      {...props}
      icon="mdi:warning-outline"
      className={classNames("bg-yellow-200 text-yellow-800", className)}
    />
  );
};

export const CloseBadgeConflict = ({ className }: CloseBadgeProps) => {
  return (
    <div
      className={classNames(
        "flex justify-center items-center absolute border-2 border-white -top-2 -right-2 bg-yellow-200 text-yellow-800 rounded-full",
        className
      )}>
      <Icon icon="mdi:close" size={1} />
    </div>
  );
};

export const BadgeUpdated = ({ className, ...props }: DiffBadgeProps) => {
  return (
    <BadgeUnchanged
      {...props}
      icon="mdi:circle-arrows"
      className={classNames("bg-blue-200 text-blue-800", className)}
    />
  );
};

export const CloseBadgeUpdated = ({ className }: CloseBadgeProps) => {
  return (
    <div
      className={classNames(
        "flex justify-center items-center absolute border-2 border-white -top-2 -right-2 bg-blue-200 text-blue-800 rounded-full",
        className
      )}>
      <Icon icon="mdi:close" size={1} />
    </div>
  );
};

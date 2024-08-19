import { Badge, BadgeProps } from "@/components/ui/badge";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { ReactNode } from "react";

export interface DiffBadgeProps extends BadgeProps {
  loading?: boolean;
  children?: ReactNode;
  conflicts?: boolean;
  active?: boolean;
}

export type BadgeType =
  | typeof BadgeAdd
  | typeof BadgeRemove
  | typeof BadgeUpdate
  | typeof BadgeUnchange
  | typeof BadgeConflict;

export const BadgeAdd = ({ active, loading, children, conflicts, ...props }: DiffBadgeProps) => {
  return (
    <Badge
      className={classNames(
        "flex items-center rounded-full p-0 cursor-pointer",
        active && "border border-green-900"
      )}
      variant="green"
      {...props}>
      <div className="flex items-center mx-1 my-0.5">
        <Icon
          icon="mdi:plus-circle-outline"
          className={classNames("text-xs", (loading || children) && "mr-1")}
        />
        {loading ? <LoadingScreen size={8} hideText /> : children}
      </div>
      {conflicts && (
        <div className="flex justify-center items-center rounded-full w-4 h-4 bg-yellow-100 text-yellow-900">
          <Icon icon={"mdi:warning-outline"} />
        </div>
      )}
    </Badge>
  );
};

export const BadgeRemove = ({ active, loading, children, conflicts, ...props }: DiffBadgeProps) => {
  return (
    <Badge
      className={classNames(
        "flex items-center rounded-full p-0 cursor-pointer",
        active && "border border-red-900"
      )}
      variant="red"
      {...props}>
      <div className="flex items-center mx-1 my-0.5">
        <Icon
          icon="mdi:minus-circle-outline"
          className={classNames("text-xs", (loading || children) && "mr-1")}
        />
        {loading ? <LoadingScreen size={8} hideText /> : children}
      </div>
      {conflicts && (
        <div className="flex justify-center items-center rounded-full w-4 h-4 bg-yellow-100 text-yellow-900">
          <Icon icon={"mdi:warning-outline"} />
        </div>
      )}
    </Badge>
  );
};

export const BadgeUpdate = ({ active, loading, children, conflicts, ...props }: DiffBadgeProps) => {
  return (
    <Badge
      className={classNames(
        "flex items-center rounded-full p-0 cursor-pointer",
        active && "border border-custom-blue-700"
      )}
      variant="blue"
      {...props}>
      <div className="flex items-center mx-1 my-0.5">
        <Icon
          icon="mdi:circle-arrows"
          className={classNames("text-xs", (loading || children) && "mr-1")}
        />
        {loading ? <LoadingScreen size={8} hideText /> : children}
      </div>
      {conflicts && (
        <div className="flex justify-center items-center rounded-full w-4 h-4 bg-yellow-100 text-yellow-900">
          <Icon icon={"mdi:warning-outline"} />
        </div>
      )}
    </Badge>
  );
};

export const BadgeUnchange = ({ loading, children, conflicts, ...props }: DiffBadgeProps) => {
  return (
    <Badge
      className={classNames("flex items-center rounded-full p-0 cursor-pointer")}
      variant={"white"}
      {...props}>
      <div className="flex items-center mx-1 my-0.5">
        <Icon icon="mdi:check" className={classNames("text-xs", (loading || children) && "mr-1")} />
        {loading ? <LoadingScreen size={8} hideText /> : children}
      </div>
      {conflicts && (
        <div className="flex justify-center items-center rounded-full w-4 h-4 bg-yellow-100 text-yellow-900">
          <Icon icon={"mdi:warning-outline"} />
        </div>
      )}
    </Badge>
  );
};

export const BadgeConflict = ({ active, loading, children, ...props }: DiffBadgeProps) => {
  return (
    <Badge
      className={classNames(
        "flex items-center rounded-full p-0 cursor-pointer",
        active && "border border-yellow-900"
      )}
      variant="yellow"
      {...props}>
      <div className="flex items-center mx-1 my-0.5">
        <Icon
          icon="mdi:warning-outline"
          className={classNames("text-xs", (loading || children) && "mr-1")}
        />
        {loading ? <LoadingScreen size={8} hideText /> : children}
      </div>
    </Badge>
  );
};

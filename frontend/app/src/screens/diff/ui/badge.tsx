import { Badge } from "@/components/ui/badge";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { ReactNode } from "react";

type BadgeProps = {
  loading?: boolean;
  children?: ReactNode;
  conflicts?: boolean;
};

export type BadgeType =
  | typeof BadgeAdd
  | typeof BadgeRemove
  | typeof BadgeUpdate
  | typeof BadgeUnchange
  | typeof BadgeConflict;

export const BadgeAdd = ({ loading, children, conflicts }: BadgeProps) => {
  return (
    <Badge className="flex items-center rounded-full p-0" variant="green">
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

export const BadgeRemove = ({ loading, children, conflicts }: BadgeProps) => {
  return (
    <Badge className="flex items-center rounded-full p-0" variant="red">
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

export const BadgeUpdate = ({ loading, children, conflicts }: BadgeProps) => {
  return (
    <Badge className="flex items-center rounded-full p-0" variant="blue">
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

export const BadgeUnchange = ({ loading, children, conflicts }: BadgeProps) => {
  return (
    <Badge className="flex items-center rounded-full p-0" variant={"white"}>
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

export const BadgeConflict = ({ loading, children }: BadgeProps) => {
  return (
    <Badge className="flex items-center rounded-full p-0" variant="yellow">
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

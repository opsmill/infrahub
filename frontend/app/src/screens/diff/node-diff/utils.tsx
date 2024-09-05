import {
  BadgeAdded,
  BadgeConflict,
  BadgeRemoved,
  BadgeType,
  BadgeUnchanged,
  BadgeUpdated,
  DiffBadgeProps,
} from "../diff-badge";
import { ReactNode } from "react";
import { DiffProperty, DiffStatus } from "@/screens/diff/node-diff/types";
import { classNames, warnUnexpectedType } from "@/utils/common";
import Accordion from "@/components/display/accordion";
import { capitalizeFirstLetter } from "@/utils/string";

export const diffBadges: { [key: string]: BadgeType } = {
  ADDED: BadgeAdded,
  UPDATED: BadgeUpdated,
  REMOVED: BadgeRemoved,
  UNCHANGED: BadgeUnchanged,
  CONFLICT: BadgeConflict,
};

export const DiffBadge = ({
  status,
  size = "default",
  children,
  ...props
}: DiffBadgeProps & { status: string; size?: "icon" | "default" }) => {
  const DiffBadgeComp = diffBadges[status];

  if (!DiffBadgeComp) {
    return null;
  }

  return (
    <DiffBadgeComp {...props}>
      {size !== "icon" && (children ?? capitalizeFirstLetter(status))}
    </DiffBadgeComp>
  );
};

type DiffRowProps = {
  title: ReactNode;
  left?: ReactNode;
  leftClassName?: string;
  right?: ReactNode;
  rightClassName?: string;
  hasConflicts?: boolean;
  children?: ReactNode;
  iconClassName?: string;
  status: DiffStatus;
};
export const DiffRow = ({
  children,
  hasConflicts,
  title,
  left,
  leftClassName,
  right,
  rightClassName,
  iconClassName,
  status,
}: DiffRowProps) => {
  return (
    <div className={classNames("min-h-9 relative", hasConflicts && "bg-yellow-50")}>
      {hasConflicts && <div className="absolute top-0 bottom-0 left-0 w-0.5 bg-yellow-400" />}

      <Accordion
        defaultOpen={hasConflicts}
        iconClassName={classNames("absolute", iconClassName)}
        hideChevron={!children}
        title={
          <div className={classNames("grid grid-cols-3 text-xs font-normal group pl-8")}>
            {title}

            <div className="bg-custom-white">
              <div className={classNames("bg-gray-50 p-2 flex items-center h-full", leftClassName)}>
                {left}
              </div>
            </div>

            <div className="bg-custom-white">
              <div
                className={classNames(
                  "p-2 flex items-center h-full font-medium",
                  status === "ADDED" && "bg-green-100 text-green-900",
                  status === "REMOVED" && "bg-red-100 text-red-900",
                  status === "UPDATED" && "bg-blue-100 text-blue-900",
                  rightClassName
                )}>
                {right}
              </div>
            </div>
          </div>
        }>
        {children}
      </Accordion>
    </div>
  );
};

export const formatValue = (value: any) => {
  if (value === "NULL") return "-";

  return value;
};

export const formatPropertyName = (name: DiffProperty["property_type"]) => {
  switch (name) {
    case "HAS_OWNER":
      return "owner";
    case "HAS_SOURCE":
      return "source";
    case "HAS_VALUE":
      return "value";
    case "IS_PROTECTED":
      return "protected";
    case "IS_VISIBLE":
      return "visible";
    case "IS_RELATED":
      return "ID";
    default: {
      warnUnexpectedType(name);
      return name;
    }
  }
};

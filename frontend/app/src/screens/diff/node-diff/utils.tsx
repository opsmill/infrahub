import {
  BadgeAdded,
  BadgeRemoved,
  BadgeType,
  BadgeUnchanged,
  BadgeUpdated,
  DiffBadgeProps,
} from "../diff-badge";
import { ReactNode } from "react";
import { DiffProperty } from "@/screens/diff/node-diff/types";
import { classNames, warnUnexpectedType } from "@/utils/common";
import Accordion from "@/components/display/accordion";
import { capitalizeFirstLetter } from "@/utils/string";

export const diffBadges: { [key: string]: BadgeType } = {
  ADDED: BadgeAdded,
  UPDATED: BadgeUpdated,
  REMOVED: BadgeRemoved,
  UNCHANGED: BadgeUnchanged,
};

export const DiffBadge = ({
  status,
  icon,
  children,
  ...props
}: DiffBadgeProps & { status: string; icon?: boolean }) => {
  const DiffBadgeComp = diffBadges[status];

  if (!DiffBadgeComp) {
    return null;
  }

  return (
    <DiffBadgeComp {...props}>{!icon && (children ?? capitalizeFirstLetter(status))}</DiffBadgeComp>
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
};
export const DiffRow = ({
  children,
  hasConflicts,
  title,
  left,
  leftClassName,
  right,
  rightClassName,
}: DiffRowProps) => {
  return (
    <div className={classNames("bg-custom-white min-h-9 relative", hasConflicts && "bg-yellow-50")}>
      {hasConflicts && <div className="absolute top-0 bottom-0 left-0 w-0.5 bg-yellow-400" />}

      <Accordion
        hideChevron={!children}
        title={
          <div
            className={classNames(
              "grid grid-cols-3 text-xs font-normal group",
              !children && "pl-8"
            )}>
            {title}

            <div
              className={classNames(
                "bg-green-700/10 p-2 flex items-center",
                leftClassName,
                hasConflicts && "bg-yellow-50"
              )}>
              {left}
            </div>

            <div
              className={classNames(
                "bg-custom-blue-700/10 p-2 flex items-center",
                rightClassName,
                hasConflicts && "bg-yellow-50"
              )}>
              {right}
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

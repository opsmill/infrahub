import type { ReactNode } from "react";

import type { DiffTreeQueryFilters } from "@/shared/api/graphql/generated/graphql";
import Accordion from "@/shared/components/display/accordion";
import { classNames, warnUnexpectedType } from "@/shared/utils/common";
import { capitalizeFirstLetter } from "@/shared/utils/string";

import { DIFF_STATUS, type DiffProperty, type DiffStatus } from "@/entities/diff/node-diff/types";
import {
  BadgeAdded,
  BadgeConflict,
  BadgeRemoved,
  type BadgeType,
  BadgeUnchanged,
  BadgeUpdated,
  type DiffBadgeProps,
} from "@/entities/diff/ui/diff-badge";
import type { DiffFilter } from "@/entities/proposed-changes/ui/diff-filter";

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
  className?: string;
  title: ReactNode;
  left?: ReactNode;
  leftClassName?: string;
  right?: ReactNode;
  rightClassName?: string;
  hasConflicts?: boolean;
  children?: ReactNode;
  iconClassName?: string;
  status?: DiffStatus;
};

const DiffDisplay = ({
  hasConflicts,
  title,
  status,
  className,
  left,
  leftClassName,
  right,
  rightClassName,
}: DiffRowProps) => {
  return (
    <div className={classNames("relative min-h-9", hasConflicts && "bg-yellow-50")}>
      {hasConflicts && <div className="absolute top-0 bottom-0 left-0 w-0.5 bg-yellow-400" />}

      <div className={classNames("group grid grid-cols-3 pl-8 font-normal text-xs", className)}>
        {title}

        <div className="bg-white">
          <div className={classNames("flex h-full items-center bg-gray-50 p-2", leftClassName)}>
            {left}
          </div>
        </div>

        <div className="bg-white">
          <div
            className={classNames(
              "flex h-full items-center p-2 font-medium",
              status === "ADDED" && "bg-green-100 text-green-900",
              status === "REMOVED" && "bg-red-100 text-red-900",
              status === "UPDATED" && "bg-blue-100 text-blue-900",
              rightClassName
            )}
          >
            {right}
          </div>
        </div>
      </div>
    </div>
  );
};

export const DiffRow = ({ children, iconClassName, ...props }: DiffRowProps) => {
  const { hasConflicts } = props;

  if (!children) {
    return <DiffDisplay {...props} />;
  }

  return (
    <div className={classNames("relative min-h-9", hasConflicts && "bg-yellow-50")}>
      {hasConflicts && <div className="absolute top-0 bottom-0 left-0 w-0.5 bg-yellow-400" />}

      <Accordion
        defaultOpen={hasConflicts}
        iconClassName={classNames("absolute", iconClassName)}
        hideChevron={!children}
        title={<DiffDisplay {...props} />}
      >
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
    case "IS_RELATED":
      return "ID";
    default: {
      warnUnexpectedType(name);
      return name;
    }
  }
};

// Handle QSP to filter from the status
export const buildFilters = (filters: DiffFilter, qsp?: string | null): DiffTreeQueryFilters => {
  const statusFilter = {
    ...filters?.status,
    includes: Array.from(
      // CONFLICT should not be part of the status filters
      new Set([...(filters?.status?.includes ?? []), qsp !== DIFF_STATUS.CONFLICT && qsp])
    ).filter((value) => !!value),
  };

  return {
    ...filters,
    status: statusFilter,
  } as DiffTreeQueryFilters;
};

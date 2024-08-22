import { capitalizeFirstLetter } from "@/utils/string";
import { BadgeAdded, BadgeRemoved, BadgeType, BadgeUnchanged, BadgeUpdated } from "../diff-badge";
import { ReactNode } from "react";
import { DiffProperty } from "@/screens/diff/node-diff/types";
import { classNames, warnUnexpectedType } from "@/utils/common";
import Accordion from "@/components/display/accordion";

export const diffBadges: { [key: string]: BadgeType } = {
  ADDED: BadgeAdded,
  UPDATED: BadgeUpdated,
  REMOVED: BadgeRemoved,
  UNCHANGED: BadgeUnchanged,
};

type DiffTitleProps = {
  status: string;
  containsConflict?: boolean;
  children?: ReactNode;
};

export const DiffTitle = ({ status, containsConflict, children }: DiffTitleProps) => {
  const DiffBadge = diffBadges[status];

  return (
    <div className="flex items-center relative group">
      <div className="flex min-w-[100px]">
        <DiffBadge conflicts={containsConflict}>{capitalizeFirstLetter(status)}</DiffBadge>
      </div>

      {children}
    </div>
  );
};

type DiffRowProps = {
  title: ReactNode;
  left?: ReactNode;
  right?: ReactNode;
  hasConflicts?: boolean;
  children?: ReactNode;
};
export const DiffRow = ({ children, hasConflicts, title, left, right }: DiffRowProps) => {
  return (
    <div className={classNames("bg-custom-white relative", hasConflicts && "bg-yellow-50")}>
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

            <div className="bg-green-700/10 p-2">{left}</div>

            <div className="bg-custom-blue-700/10 p-2">{right}</div>
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

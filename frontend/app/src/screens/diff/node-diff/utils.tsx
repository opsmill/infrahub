import { capitalizeFirstLetter } from "@/utils/string";
import { BadgeAdded, BadgeRemoved, BadgeType, BadgeUnchanged, BadgeUpdated } from "../diff-badge";
import { ReactElement, ReactNode } from "react";
import { DiffProperty } from "@/screens/diff/node-diff/types";
import { warnUnexpectedType } from "@/utils/common";

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

type DiffDisplayProps = {
  left?: ReactElement;
  right?: ReactElement;
};

export const DiffDisplay = ({ left, right }: DiffDisplayProps) => {
  return (
    <div className="flex h-8 bg-custom-white">
      <div className="flex-1 px-2 bg-green-700/10">{left}</div>

      <div className="flex-1 px-2 bg-custom-blue-700/10 ">{right}</div>
    </div>
  );
};
type DiffRowProps = {
  title: ReactElement;
  left: ReactElement;
  right: ReactElement;
};
export const DiffRow = ({ title, left, right }: DiffRowProps) => {
  return (
    <div className="grid grid-cols-3 text-xs font-normal group">
      {title}

      <div className="bg-green-700/10 p-2">{left}</div>

      <div className="bg-custom-blue-700/10 p-2">{right}</div>
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
    default: {
      warnUnexpectedType(name);
      return name;
    }
  }
};

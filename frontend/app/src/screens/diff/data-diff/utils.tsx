import { capitalizeFirstLetter } from "@/utils/string";
import { BadgeAdd, BadgeRemove, BadgeType, BadgeUnchange, BadgeUpdate } from "../ui/badge";
import { useParams } from "react-router-dom";
import { DiffThread } from "./thread";
import { ReactElement, ReactNode } from "react";

export const diffBadges: { [key: string]: BadgeType } = {
  ADDED: BadgeAdd,
  UPDATED: BadgeUpdate,
  REMOVED: BadgeRemove,
  UNCHANGED: BadgeUnchange,
};

type DiffTitleProps = {
  id?: string;
  status: string;
  containsConflict?: boolean;
  children?: ReactNode;
};

export const DiffTitle = ({ id, status, containsConflict, children }: DiffTitleProps) => {
  const { "*": branchName } = useParams();

  const DiffBadge = diffBadges[status];

  return (
    <div className="flex items-center relative group">
      <div className="flex min-w-[100px]">
        <DiffBadge conflicts={containsConflict}>{capitalizeFirstLetter(status)}</DiffBadge>
      </div>

      {children}

      {!branchName && id && <DiffThread path={`data/${id}`} />}
    </div>
  );
};

type DiffDisplayProps = {
  left?: ReactElement;
  right?: ReactElement;
};

export const DiffDisplay = ({ left, right }: DiffDisplayProps) => {
  return (
    <div className="flex h-7 bg-custom-white">
      <div className="flex-1 px-2 bg-green-700/10">{left}</div>

      <div className="flex-1 px-2 bg-custom-blue-700/10 ">{right}</div>
    </div>
  );
};

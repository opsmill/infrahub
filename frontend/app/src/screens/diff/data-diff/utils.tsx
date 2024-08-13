import { capitalizeFirstLetter } from "@/utils/string";
import { BadgeAdd, BadgeRemove, BadgeType, BadgeUnchange, BadgeUpdate } from "../ui/badge";
import { useParams } from "react-router-dom";
import { DiffThread } from "./thread";
import { ReactNode } from "react";

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
    <div className="relative group grid">
      <div className="">
        <DiffBadge conflicts={containsConflict}>{capitalizeFirstLetter(status)}</DiffBadge>
      </div>

      {children}

      {!branchName && id && <DiffThread path={`data/${id}`} />}
    </div>
  );
};

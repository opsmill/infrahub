import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { Link } from "react-router";

import { Badge } from "@/shared/components/ui/badge";
import { Id } from "@/shared/components/ui/id";
import { QSP } from "@/shared/config/qsp";
import { classNames } from "@/shared/utils/common";

import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";

import { DiffRow } from "@/entities/diff/ui/node-diff/utils";
import { BadgeConflict } from "@/entities/diff/ui/diff-badge";

type Change = {
  branch: string;
  previous: string;
  new: string;
};

type DataConflictProps = {
  id: string;
  kind: string;
  name: string;
  changes: Array<Change>;
};

export const DataConflict = ({ id, changes, kind, name }: DataConflictProps) => {
  const proposedChangesDetails = useAtomValue(proposedChangedState);
  const schemaLabels = useAtomValue(schemaKindLabelState);

  if (!changes) {
    return null;
  }

  const url = `/proposed-changes/${proposedChangesDetails.id}?${QSP.PROPOSED_CHANGES_TAB}=data#${id}`;

  const mainChange = changes.find((change) => {
    return change.branch === "main";
  });

  const branchChange = changes.find((change) => {
    return change.branch !== "main";
  });

  return (
    <div>
      <div className="mb-2 flex items-center">
        <Badge className="mr-2">{schemaLabels[kind]}</Badge>

        <Id id={id} kind={kind} />
      </div>

      <Link to={url}>
        <DiffRow
          className="group overflow-hidden rounded-sm pl-0 transition-all hover:bg-yellow-100"
          iconClassName="left-4"
          hasConflicts
          title={
            <div className={classNames("flex items-center justify-between pr-2 pl-4")}>
              <div className="flex items-center gap-2 py-3 font-semibold">
                {name}
                <BadgeConflict>Conflict</BadgeConflict>
              </div>
            </div>
          }
          left={
            <div className="flex items-center gap-2">
              {mainChange?.previous}
              <Icon icon="mdi:chevron-right" />
              <Badge variant="yellow" className="font-medium">
                {mainChange?.new}
              </Badge>
            </div>
          }
          leftClassName={classNames("font-normal group-hover:bg-gray-100 transition-all")}
          right={
            <div className="flex items-center gap-2">
              {branchChange?.previous}
              <Icon icon="mdi:chevron-right" />
              <Badge variant="yellow" className="font-medium">
                {branchChange?.new}
              </Badge>
            </div>
          }
          rightClassName={classNames("font-normal group-hover:bg-gray-50 transition-all")}
        />
      </Link>
    </div>
  );
};

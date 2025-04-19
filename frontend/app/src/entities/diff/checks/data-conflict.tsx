import { QSP } from "@/config/qsp";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { Badge } from "@/shared/components/ui/badge";
import { Id } from "@/shared/components/ui/id";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";

import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import { Link } from "react-router";
import { DiffRow } from "../node-diff/utils";
import { BadgeConflict } from "../ui/diff-badge";

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
      <div className="flex items-center mb-2">
        <Badge className="mr-2">{schemaLabels[kind]}</Badge>

        <Id id={id} kind={kind} />
      </div>

      <Link to={url}>
        <DiffRow
          className="group pl-0 rounded-sm overflow-hidden hover:bg-yellow-100 transition-all"
          iconClassName="left-4"
          hasConflicts
          title={
            <div className={classNames("flex items-center justify-between pl-4 pr-2")}>
              <div className="flex items-center py-3 gap-2 font-semibold">
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

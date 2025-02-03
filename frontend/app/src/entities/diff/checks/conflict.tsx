import { Badge } from "@/shared/components/ui/badge";
import { Id } from "@/shared/components/ui/id";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { BadgeConflict } from "../diff-badge";
import { DiffRow } from "../node-diff/utils";

export const Conflict = ({ changes, kind, name, node_id }: any) => {
  const mainChange = changes.find((change) => {
    return change.branch === "main";
  });

  const branchChange = changes.find((change) => {
    return change.branch !== "main";
  });

  return (
    <div>
      <div className="flex items-center mb-2">
        <Badge className="mr-2">{kind}</Badge>

        <Id id={node_id} kind={kind} />
      </div>

      <DiffRow
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
            {mainChange.previous}
            <Icon icon="mdi:chevron-right" />
            <Badge variant="yellow" className="font-medium">
              {mainChange.new}
            </Badge>
          </div>
        }
        leftClassName="font-normal"
        right={
          <div className="flex items-center gap-2">
            {branchChange.previous}
            <Icon icon="mdi:chevron-right" />
            <Badge variant="yellow" className="font-medium">
              {branchChange.new}
            </Badge>
          </div>
        }
        rightClassName="font-normal"
      />
    </div>
  );
};

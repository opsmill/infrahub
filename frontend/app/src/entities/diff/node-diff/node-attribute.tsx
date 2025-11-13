import { useLocation, useParams } from "react-router";

import { Conflict } from "@/entities/diff/node-diff/conflict";
import { DiffNodeProperty } from "@/entities/diff/node-diff/node-property";
import { DiffThread } from "@/entities/diff/node-diff/thread";
import type { DiffAttribute, DiffStatus } from "@/entities/diff/node-diff/types";
import { DiffRow } from "@/entities/diff/node-diff/utils";
import { BadgeConflict } from "@/entities/diff/ui/diff-badge";

type DiffNodeAttributeProps = {
  attribute: DiffAttribute;
  status: DiffStatus;
  previousValue?: string;
  newValue?: string;
};

export const DiffNodeAttribute = ({
  attribute,
  previousValue,
  newValue,
  status,
}: DiffNodeAttributeProps) => {
  const { "*": branchName } = useParams();
  const { pathname } = useLocation();

  return (
    <DiffRow
      status={status}
      hasConflicts={attribute.contains_conflict}
      title={
        <div className="flex items-center justify-between pr-2">
          <div className="flex items-center gap-2 py-3 font-semibold">
            {attribute.name}
            {attribute.conflict && <BadgeConflict>Conflict</BadgeConflict>}
          </div>

          {!branchName && attribute.path_identifier && (
            <DiffThread path={attribute.path_identifier} />
          )}
        </div>
      }
      left={previousValue}
      right={newValue}
    >
      <div className="divide-y divide-gray-200 border-gray-200 border-t">
        {attribute.conflict && pathname.includes("/proposed-changes") && (
          <Conflict
            id={attribute.conflict.uuid}
            selectedBranch={attribute.conflict.selected_branch}
          />
        )}

        {attribute.properties.map((property, index: number) => (
          <DiffNodeProperty key={index} property={property} status={status} />
        ))}
      </div>
    </DiffRow>
  );
};

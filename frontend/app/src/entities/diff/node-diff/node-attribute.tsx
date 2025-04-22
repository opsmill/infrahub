import { DataConflict } from "@/entities/diff/checks/data-conflict";
import { DiffNodeProperty } from "@/entities/diff/node-diff/node-property";
import { DiffThread } from "@/entities/diff/node-diff/thread";
import { DiffAttribute, DiffStatus } from "@/entities/diff/node-diff/types";
import { DiffRow } from "@/entities/diff/node-diff/utils";
import { useParams } from "react-router";
import { BadgeConflict } from "../ui/diff-badge";

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

  return (
    <DiffRow
      status={status}
      hasConflicts={attribute.contains_conflict}
      title={
        <div className="flex justify-between items-center pr-2">
          <div className="flex items-center py-3 gap-2 font-semibold">
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
      <div className="divide-y border-t border-gray-200 divide-gray-200">
        {attribute.conflict && <DataConflict conflict={attribute.conflict} />}

        {attribute.properties.map((property, index: number) => (
          <DiffNodeProperty key={index} property={property} status={status} />
        ))}
      </div>
    </DiffRow>
  );
};

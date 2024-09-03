import { useParams } from "react-router-dom";
import { DiffRow } from "@/screens/diff/node-diff/utils";
import { DiffAttribute, DiffStatus } from "@/screens/diff/node-diff/types";
import { DiffThread } from "@/screens/diff/node-diff/thread";
import { DiffNodeProperty } from "@/screens/diff/node-diff/node-property";

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
          <div className="py-3 font-semibold">{attribute.name}</div>

          {!branchName && attribute.path_identifier && (
            <DiffThread path={attribute.path_identifier} />
          )}
        </div>
      }
      left={previousValue}
      right={newValue}>
      <div className="divide-y border-t">
        {attribute.properties.map((property, index: number) => (
          <DiffNodeProperty key={index} property={property} status={status} />
        ))}
      </div>
    </DiffRow>
  );
};

import { useParams } from "react-router-dom";
import { DiffRow, formatValue } from "@/screens/diff/node-diff/utils";
import { DiffAttribute, DiffStatus } from "@/screens/diff/node-diff/types";
import { DiffThread } from "@/screens/diff/node-diff/thread";
import { DiffNodeProperty } from "@/screens/diff/node-diff/node-property";

type DiffNodeAttributeProps = {
  attribute: DiffAttribute;
  status: DiffStatus;
};

export const DiffNodeAttribute = ({ attribute, status }: DiffNodeAttributeProps) => {
  const { "*": branchName } = useParams();

  const valueProperty = attribute.properties.find(
    ({ property_type }) => property_type === "HAS_VALUE"
  );

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
      left={valueProperty?.previous_value && formatValue(valueProperty?.previous_value)}
      right={status !== "REMOVED" && formatValue(valueProperty?.new_value)}>
      <div className="divide-y border-t">
        {attribute.properties.map((property, index: number) => (
          <DiffNodeProperty key={index} property={property} status={status} />
        ))}
      </div>
    </DiffRow>
  );
};

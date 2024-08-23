import { useParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { DiffRow, formatValue } from "@/screens/diff/node-diff/utils";
import { DiffAttribute } from "@/screens/diff/node-diff/types";
import { DiffThread } from "@/screens/diff/node-diff/thread";
import { DiffNodeProperty } from "@/screens/diff/node-diff/node-property";

type DiffNodeAttributeProps = {
  attribute: DiffAttribute;
};

export const DiffNodeAttribute = ({ attribute }: DiffNodeAttributeProps) => {
  const { "*": branchName } = useParams();

  const valueProperty = attribute.properties.find(
    ({ property_type }) => property_type === "HAS_VALUE"
  );

  return (
    <DiffRow
      hasConflicts={attribute.contains_conflict}
      title={
        <div className="flex justify-between items-center pr-2">
          <div className="py-3 font-semibold">{attribute.name}</div>

          {!branchName && attribute.path_identifier && (
            <DiffThread path={attribute.path_identifier} />
          )}
        </div>
      }
      left={
        valueProperty?.previous_value && (
          <Badge variant="green" className="font-medium">
            {formatValue(valueProperty?.previous_value)}
          </Badge>
        )
      }
      right={
        <Badge variant="blue" className="font-medium">
          {formatValue(valueProperty?.new_value)}
        </Badge>
      }>
      <div className="divide-y border-t">
        {attribute.properties.map((property, index: number) => (
          <DiffNodeProperty key={index} property={property} />
        ))}
      </div>
    </DiffRow>
  );
};

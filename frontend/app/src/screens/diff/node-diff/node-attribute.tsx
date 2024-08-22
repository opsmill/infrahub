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
      title={
        <div className="flex justify-between items-center pr-2">
          <div className="p-2">{attribute.name}</div>

          {!branchName && attribute.path_identifier && (
            <DiffThread path={attribute.path_identifier} />
          )}
        </div>
      }
      left={
        valueProperty?.previous_value && (
          <Badge variant="green">{formatValue(valueProperty?.previous_value)}</Badge>
        )
      }
      right={<Badge variant="blue">{formatValue(valueProperty?.new_value)}</Badge>}>
      {attribute.properties.map((property, index: number) => (
        <DiffNodeProperty key={index} property={property} />
      ))}
    </DiffRow>
  );
};

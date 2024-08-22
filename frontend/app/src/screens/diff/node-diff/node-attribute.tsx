import { classNames } from "@/utils/common";
import Accordion from "@/components/display/accordion";
import { DiffNodeProperty } from "./node-property";
import { useParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { DiffRow, formatValue } from "@/screens/diff/node-diff/utils";
import { DiffAttribute } from "@/screens/diff/node-diff/types";
import { DiffThread } from "@/screens/diff/node-diff/thread";

type DiffNodeAttributeProps = {
  attribute: DiffAttribute;
};

export const DiffNodeAttribute = ({ attribute }: DiffNodeAttributeProps) => {
  const { "*": branchName } = useParams();

  const valueProperty = attribute.properties.find(
    ({ property_type }) => property_type === "HAS_VALUE"
  );

  return (
    <div
      className={classNames(
        "bg-custom-white relative",
        attribute.contains_conflict && "bg-yellow-50"
      )}>
      {attribute.contains_conflict && (
        <div className="absolute top-0 bottom-0 left-0 w-0.5 bg-yellow-400" />
      )}

      <Accordion
        title={
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
            right={<Badge variant="blue">{formatValue(valueProperty?.new_value)}</Badge>}
          />
        }>
        {attribute.properties.map((property, index: number) => (
          <DiffNodeProperty key={index} property={property} />
        ))}
      </Accordion>
    </div>
  );
};

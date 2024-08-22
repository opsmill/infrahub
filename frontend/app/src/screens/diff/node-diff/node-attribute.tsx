import { classNames } from "@/utils/common";
import Accordion from "@/components/display/accordion";
import { DiffNodeProperty } from "./node-property";
import { useParams } from "react-router-dom";
import { DiffThread } from "@/screens/diff/node-diff/thread";
import { Badge } from "@/components/ui/badge";
import { formatValue } from "@/screens/diff/node-diff/utils";

type DiffProperty = {
  last_changed_at: string;
  conflict: null;
  new_value: any;
  previous_value: any;
  property_type: "HAS_VALUE" | "HAS_OWNER" | "HAS_SOURCE" | "IS_VISIBLE" | "IS_PROTECTED";
  path_identifier: string | null;
};

type DiffNodeAttributeProps = {
  attribute: {
    name: string;
    properties: Array<DiffProperty>;
    path_identifier: string | null;
    contains_conflict: boolean;
  };
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
        <div className="absolute top-0 bottom-0 left-0 w-1 bg-yellow-200" />
      )}

      <Accordion
        title={
          <div className="grid grid-cols-3 text-xs font-normal items-center">
            <div className="flex justify-between">
              <div className="p-2">{attribute.name}</div>

              {!branchName && attribute.path_identifier && (
                <DiffThread path={attribute.path_identifier} />
              )}
            </div>

            <div className="bg-green-700/10 p-2">
              <Badge variant="green">{formatValue(valueProperty?.previous_value)}</Badge>
            </div>

            <div className="bg-custom-blue-700/10 p-2">
              <Badge variant="blue">{formatValue(valueProperty?.new_value)}</Badge>
            </div>
          </div>
        }>
        {attribute.properties.map((property, index: number) => (
          <DiffNodeProperty key={index} property={property} />
        ))}
      </Accordion>
    </div>
  );
};

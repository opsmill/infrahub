import { classNames } from "@/utils/common";
import { DiffDisplay, DiffTitle } from "./utils";
import Accordion from "@/components/display/accordion";
import { DiffNodeProperty } from "./node-property";
import { useParams } from "react-router-dom";
import { DiffThread } from "./thread";

type DiffNodeAttributeProps = {
  attribute: any;
};

export const DiffNodeAttribute = ({ attribute }: DiffNodeAttributeProps) => {
  const { "*": branchName } = useParams();
  console.log("attribute: ", attribute);

  const title = (
    <DiffTitle containsConflict={attribute.contains_conflict} status={attribute.status}>
      <div className="flex flex-1 items-center">
        <span className="w-1/3 font-normal text-xs">{attribute.name}</span>

        {!branchName && attribute.path_identifier && (
          <DiffThread path={attribute.path_identifier} />
        )}

        <div className="w-2/3">
          <DiffDisplay />
        </div>
      </div>
    </DiffTitle>
  );

  return (
    <div
      className={classNames(
        "bg-custom-white relative",
        attribute.contains_conflict && "bg-yellow-50"
      )}>
      <div
        className={classNames(
          "absolute top-0 bottom-0 left-0 w-1",
          attribute.contains_conflict && "bg-yellow-200"
        )}
      />
      <Accordion title={title}>
        {attribute.properties.map((property, index: number) => (
          <DiffNodeProperty key={index} property={property} />
        ))}
      </Accordion>
    </div>
  );
};

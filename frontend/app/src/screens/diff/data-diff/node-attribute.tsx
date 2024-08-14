import { classNames } from "@/utils/common";
import { DiffDisplay, DiffTitle } from "./utils";
import Accordion from "@/components/display/accordion";
import { DiffNodeProperty } from "./node-property";

type DiffNodeAttributeProps = {
  attribute: any;
};

export const DiffNodeAttribute = ({ attribute }: DiffNodeAttributeProps) => {
  console.log("attribute: ", attribute);
  const title = (
    <DiffTitle
      id={attribute.id}
      containsConflict={attribute.contains_conflict}
      status={attribute.status}>
      <div className="flex flex-1 items-center">
        <span className="w-1/3 font-normal text-xs">{attribute.name}</span>

        <div className="w-2/3">
          <DiffDisplay />
        </div>
      </div>
    </DiffTitle>
  );

  return (
    <div
      className={classNames(
        "border-l-4 border-transparent bg-custom-white",
        attribute.contains_conflict && "border-yellow-200 bg-yellow-50"
      )}>
      <Accordion title={title}>
        {attribute.properties.map((property, index: number) => (
          <DiffNodeProperty key={index} property={property} />
        ))}
      </Accordion>
    </div>
  );
};

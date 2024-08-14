import Accordion from "@/components/display/accordion";
import { classNames } from "@/utils/common";
import { DiffNodeElement } from "./node-element";
import { DiffDisplay, DiffTitle } from "./utils";

type DiffNodeRelationshipProps = {
  relationship: any;
};

export const DiffNodeRelationship = ({ relationship }: DiffNodeRelationshipProps) => {
  const title = (
    <DiffTitle
      id={relationship.id}
      containsConflict={relationship.contains_conflict}
      status={relationship.status}>
      <div className="flex flex-1 items-center">
        <span className="flex-1 font-normal text-xs">{relationship.name}</span>

        <div className="flex-1">
          <DiffDisplay />
        </div>
      </div>
    </DiffTitle>
  );

  return (
    <div
      className={classNames(
        "border-l-4 border-transparent bg-custom-white",
        relationship.contains_conflict && "border-yellow-200 bg-yellow-50"
      )}>
      <Accordion title={title}>
        {relationship.elements.map((element, index: number) => (
          <DiffNodeElement key={index} element={element} />
        ))}
      </Accordion>
    </div>
  );
};

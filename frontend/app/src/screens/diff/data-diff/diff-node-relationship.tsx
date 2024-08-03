import Accordion from "@/components/display/accordion";
import { classNames } from "@/utils/common";
import { BadgeConflict } from "../ui/badge";

type DiffNodeRelationshipProps = {
  relationship: any;
};

export const DiffNodeRelationship = ({ relationship }: DiffNodeRelationshipProps) => {
  const title = (
    <div className="flex items-center gap-2">
      {relationship.contains_conflict && <BadgeConflict />}
      <span className="text-xs">{relationship.name}</span>
    </div>
  );

  return (
    <div
      className={classNames(
        "border-l-4 border-transparent",
        relationship.contains_conflict && "border-yellow-200 bg-yellow-50"
      )}>
      <Accordion title={title}>ok here</Accordion>
    </div>
  );
};

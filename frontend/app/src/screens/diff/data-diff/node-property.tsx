import { EmptyAccordion } from "@/components/display/accordion";
import { DiffDisplay, DiffTitle } from "./utils";

import { Badge } from "@/components/ui/badge";

type DiffNodePropertyProps = {
  property: any;
};

export const DiffNodeProperty = ({ property }: DiffNodePropertyProps) => {
  const previousValue = property.previous_value && (
    <Badge variant={"green-outline"}>{property.previous_value}</Badge>
  );
  const newValue = property.new_value && (
    <Badge variant={"blue-outline"}>{property.new_value}</Badge>
  );

  const title = (
    <DiffTitle status={property.status}>
      <div className="flex flex-1 items-center">
        <span className="flex-1 font-normal text-xs">{property.property_type}</span>

        <div className="flex-1">
          <DiffDisplay left={previousValue} right={newValue} />
        </div>
      </div>
    </DiffTitle>
  );

  return <EmptyAccordion title={title} iconClassName="text-transparent" />;
};

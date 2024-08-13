import { EmptyAccordion } from "@/components/display/accordion";
import { DiffTitle } from "./utils";
import { Badge } from "@/components/ui/badge";
import { DiffDisplay } from "./diff-display";

type DiffNodePropertyProps = {
  property: any;
};

export const DiffNodeProperty = ({ property }: DiffNodePropertyProps) => {
  console.log("property: ", property);

  const title = (
    <DiffTitle status={property.status}>
      <div className="flex flex-1 items-center">
        <div className="flex-1">
          <Badge variant={"white"}>{property.property_type}</Badge>
        </div>

        <div className="flex-1">
          <DiffDisplay />
        </div>
      </div>
    </DiffTitle>
  );

  return <EmptyAccordion title={title} iconClassName="text-transparent" />;
};

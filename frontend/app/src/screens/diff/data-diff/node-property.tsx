import { EmptyAccordion } from "@/components/display/accordion";
import { DiffDisplay, DiffTitle } from "./utils";

import { Badge } from "@/components/ui/badge";
import { useParams } from "react-router-dom";
import { DiffThread } from "./thread";

type DiffNodePropertyProps = {
  property: any;
};

export const DiffNodeProperty = ({ property }: DiffNodePropertyProps) => {
  const { "*": branchName } = useParams();
  console.log("property: ", property);
  if (property.status === "UNCHANGED") return;

  const previousValue = property.previous_value && (
    <Badge variant={"green-outline"}>{property.previous_value}</Badge>
  );
  const newValue = property.new_value && (
    <Badge variant={"blue-outline"}>{property.new_value}</Badge>
  );

  const title = (
    <DiffTitle status={property.status}>
      <div className="flex flex-1 items-center group">
        <div className="flex items-center w-1/3 font-normal text-xs">
          {property.property_type}

          {!branchName && property.path_identifier && (
            <DiffThread path={property.path_identifier} />
          )}
        </div>

        <div className="w-2/3">
          <DiffDisplay left={previousValue} right={newValue} />
        </div>
      </div>
    </DiffTitle>
  );

  return <EmptyAccordion title={title} iconClassName="text-transparent" />;
};

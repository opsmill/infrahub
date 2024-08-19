import Accordion, { EmptyAccordion } from "@/components/display/accordion";
import { DiffDisplay, DiffTitle } from "./utils";

import { Badge } from "@/components/ui/badge";
import { useParams } from "react-router-dom";
import { DiffThread } from "./thread";
import { Icon } from "@iconify-icon/react";
import { Conflict } from "./conflict";

type DiffNodePropertyProps = {
  property: any;
};

const getPreviousValue = (property) => {
  if (!property.conflict) {
    return <Badge variant={"green-outline"}>{property.previous_value}</Badge>;
  }

  return (
    <div className="flex items-center gap-2">
      <Badge variant={"green-outline"}>{property.previous_value}</Badge>

      <Icon icon={"mdi:chevron-right"} />

      <Badge variant={"green-outline"}>{property.conflict.base_branch_value}</Badge>
    </div>
  );
};

const getNewValue = (property) => {
  if (!property.conflict) {
    return <Badge variant={"green-outline"}>{property.new_value}</Badge>;
  }

  return (
    <div className="flex items-center gap-2">
      <Badge variant={"blue-outline"}>{property.previous_value}</Badge>

      <Icon icon={"mdi:chevron-right"} />

      <Badge variant={"blue-outline"}>{property.conflict.diff_branch_value}</Badge>
    </div>
  );
};

export const DiffNodeProperty = ({ property }: DiffNodePropertyProps) => {
  const { "*": branchName } = useParams();

  const title = (
    <DiffTitle status={property.status} containsConflict={property.conflict}>
      <div className="flex flex-1 items-center group">
        <div className="flex items-center w-1/3 font-normal text-xs">
          {property.property_type}

          {!branchName && property.path_identifier && (
            <DiffThread path={property.path_identifier} />
          )}
        </div>

        <div className="w-2/3">
          <DiffDisplay left={getPreviousValue(property)} right={getNewValue(property)} />
        </div>
      </div>
    </DiffTitle>
  );

  if (!property.conflict) return <EmptyAccordion title={title} iconClassName="text-transparent" />;

  return (
    <Accordion title={title}>
      <Conflict conflict={property.conflict} id={property.path_identifier} />
    </Accordion>
  );
};

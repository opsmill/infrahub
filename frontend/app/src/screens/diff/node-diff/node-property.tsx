import Accordion, { EmptyAccordion } from "@/components/display/accordion";

import { Badge } from "@/components/ui/badge";
import { useParams } from "react-router-dom";
import { DiffThread } from "./thread";
import { Icon } from "@iconify-icon/react";
import { Conflict } from "./conflict";
import { DiffRow, formatPropertyName, formatValue } from "@/screens/diff/node-diff/utils";
import { BadgeConflict } from "@/screens/diff/diff-badge";
import { DiffProperty } from "@/screens/diff/node-diff/types";

type DiffNodePropertyProps = {
  property: DiffProperty;
};

const getPreviousValue = (property: DiffProperty) => {
  const previousValue = formatValue(property.previous_value);
  if (previousValue === null) return null;

  if (!property.conflict) {
    return <Badge variant="green">{previousValue}</Badge>;
  }

  const conflictValue = formatValue(property.conflict.base_branch_value);
  return (
    <div className="flex items-center gap-2">
      <Badge variant="green">{previousValue}</Badge>
      <Icon icon="mdi:chevron-right" />
      <Badge variant="yellow">{conflictValue}</Badge>
    </div>
  );
};

const getNewValue = (property: DiffProperty) => {
  const newValue = formatValue(property.new_value);
  if (!property.conflict) {
    return <Badge variant="blue">{newValue}</Badge>;
  }

  const conflictValue = formatValue(property.conflict.diff_branch_value);
  return <Badge variant="yellow">{conflictValue}</Badge>;
};

export const DiffNodeProperty = ({ property }: DiffNodePropertyProps) => {
  const { "*": branchName } = useParams();

  const title = (
    <DiffRow
      title={
        <div className="flex items-center justify-between pl-8 pr-2">
          <div className="flex items-center gap-2">
            {formatPropertyName(property.property_type)} {property.status}
            {property.conflict && <BadgeConflict>Conflict</BadgeConflict>}
          </div>

          {!branchName && property.path_identifier && (
            <DiffThread path={property.path_identifier} />
          )}
        </div>
      }
      left={getPreviousValue(property)}
      right={getNewValue(property)}
    />
  );

  if (!property.conflict) return <EmptyAccordion title={title} iconClassName="text-transparent" />;

  return (
    <Accordion title={title}>
      <Conflict conflict={property.conflict} />
    </Accordion>
  );
};

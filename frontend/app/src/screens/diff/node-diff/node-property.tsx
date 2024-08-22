import Accordion, { EmptyAccordion } from "@/components/display/accordion";

import { Badge } from "@/components/ui/badge";
import { useParams } from "react-router-dom";
import { DiffThread } from "./thread";
import { Icon } from "@iconify-icon/react";
import { Conflict } from "./conflict";
import { formatValue } from "@/screens/diff/node-diff/utils";
import { BadgeConflict } from "@/screens/diff/diff-badge";

type DiffNodePropertyProps = {
  property: any;
};

const getPreviousValue = (property) => {
  const previousValue = formatValue(property.previous_value);
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

const getNewValue = (property) => {
  const previousValue = formatValue(property.previous_value);
  if (!property.conflict) {
    return <Badge variant="blue">{previousValue}</Badge>;
  }

  const conflictValue = formatValue(property.conflict.diff_branch_value);
  return <Badge variant="yellow">{conflictValue}</Badge>;
};

export const DiffNodeProperty = ({ property }: DiffNodePropertyProps) => {
  const { "*": branchName } = useParams();

  const title = (
    <div className="grid grid-cols-3 text-xs font-normal group">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {property.property_type}
          {property.conflict && <BadgeConflict>Conflict</BadgeConflict>}
        </div>

        {!branchName && property.path_identifier && <DiffThread path={property.path_identifier} />}
      </div>

      <div className="bg-green-700/10 p-2">{getPreviousValue(property)}</div>

      <div className="bg-custom-blue-700/10 p-2">{getNewValue(property)}</div>
    </div>
  );

  if (!property.conflict) return <EmptyAccordion title={title} iconClassName="text-transparent" />;

  return (
    <Accordion title={title}>
      <Conflict conflict={property.conflict} />
    </Accordion>
  );
};

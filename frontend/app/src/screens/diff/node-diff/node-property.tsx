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
    return (
      <Badge variant="green" className="bg-transparent">
        {previousValue}
      </Badge>
    );
  }

  const conflictValue = formatValue(property.conflict.base_branch_value);
  return (
    <div className="flex items-center gap-2">
      <Badge variant="green" className="bg-transparent">
        {previousValue}
      </Badge>
      <Icon icon="mdi:chevron-right" />
      <Badge variant="yellow">{conflictValue}</Badge>
    </div>
  );
};

const getNewValue = (property: DiffProperty) => {
  const newValue = formatValue(property.new_value);
  if (newValue === null) return null;

  if (!property.conflict) {
    return (
      <Badge variant="blue" className="bg-transparent">
        {newValue}
      </Badge>
    );
  }

  const conflictValue = formatValue(property.conflict.diff_branch_value);
  return <Badge variant="yellow">{conflictValue}</Badge>;
};

export const DiffNodeProperty = ({ property }: DiffNodePropertyProps) => {
  const { "*": branchName } = useParams();

  return (
    <DiffRow
      hasConflicts={!!property.conflict}
      title={
        <div className="flex items-center justify-between pl-8 pr-2">
          <div className="flex items-center py-3 gap-2">
            {formatPropertyName(property.property_type)}
            {property.conflict && <BadgeConflict>Conflict</BadgeConflict>}
          </div>

          {!branchName && property.path_identifier && (
            <DiffThread path={property.path_identifier} />
          )}
        </div>
      }
      left={getPreviousValue(property)}
      leftClassName="bg-green-400/10"
      right={getNewValue(property)}
      rightClassName="bg-custom-blue-400/10">
      {property.conflict && <Conflict conflict={property.conflict} />}
    </DiffRow>
  );
};

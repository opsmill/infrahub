import { Badge } from "@/components/ui/badge";
import { BadgeConflict } from "@/screens/diff/diff-badge";
import { DiffProperty, DiffStatus } from "@/screens/diff/node-diff/types";
import { DiffRow, formatPropertyName, formatValue } from "@/screens/diff/node-diff/utils";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router-dom";
import { Conflict } from "./conflict";
import { DiffThread } from "./thread";

type DiffNodePropertyProps = {
  className?: string;
  property: DiffProperty;
  status: DiffStatus;
};

export const getPreviousValue = (property: DiffProperty) => {
  const previousValue = formatValue(property.previous_value);
  if (previousValue === null) return null;

  if (!property.conflict) {
    return previousValue;
  }

  const conflictValue = formatValue(
    property.conflict.base_branch_label || property.conflict.base_branch_value
  );
  return (
    <div className="flex items-center gap-2">
      {previousValue}
      <Icon icon="mdi:chevron-right" />
      <Badge variant="yellow" className="font-medium">
        {conflictValue}
      </Badge>
    </div>
  );
};

export const getNewValue = (property: DiffProperty) => {
  const newValue = formatValue(property.new_value);
  if (newValue === null) return null;

  if (!property.conflict) {
    return newValue;
  }

  const conflictValue = formatValue(
    property.conflict.diff_branch_label || property.conflict.diff_branch_value
  );
  return (
    <Badge variant="yellow" className="font-medium">
      {conflictValue}
    </Badge>
  );
};

export const DiffNodeProperty = ({ status, property, className }: DiffNodePropertyProps) => {
  const { "*": branchName } = useParams();

  return (
    <DiffRow
      status={status}
      iconClassName="left-4"
      hasConflicts={!!property.conflict}
      title={
        <div className={classNames("flex items-center justify-between pl-4 pr-2", className)}>
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
      leftClassName="font-normal"
      rightClassName="font-normal"
      right={getNewValue(property)}
    >
      {property.conflict && <Conflict conflict={property.conflict} />}
    </DiffRow>
  );
};

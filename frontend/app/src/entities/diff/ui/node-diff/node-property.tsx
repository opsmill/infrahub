import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router";

import { Badge } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import type { DiffProperty, DiffStatus } from "@/entities/diff/ui/node-diff/types";
import { DiffRow, formatPropertyName, formatValue } from "@/entities/diff/ui/node-diff/utils";
import { BadgeConflict } from "@/entities/diff/ui/diff-badge";

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
        <div className={classNames("flex items-center justify-between pr-2 pl-4", className)}>
          <div className="flex items-center gap-2 py-3">
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
      {property.conflict && <DataConflict conflict={property.conflict} />}
    </DiffRow>
  );
};

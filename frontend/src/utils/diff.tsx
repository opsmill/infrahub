import { ChevronRightIcon } from "@heroicons/react/24/outline";
import { BADGE_TYPES, Badge } from "../components/badge";
import { Tooltip } from "../components/tooltip";
import { tDataDiffNodeProperty } from "../screens/branches/diff/data-diff-node";

export const displayValue = (value: any) => {
  if (typeof value === "boolean") {
    return `${value}`;
  }

  return value || "-";
};

// Display the values
// (only new one for "added", only old ones for "deleted", and previous + new for "updated")
export const diffContent: { [key: string]: any; } = {
  added: (property: tDataDiffNodeProperty) => {
    const { value } = property;

    const { new: newValue } = value;

    return (
      <div className="flex">
        <Badge type={BADGE_TYPES.VALIDATE}>
          {displayValue(newValue)}
        </Badge>
      </div>
    );
  },
  removed: (property: tDataDiffNodeProperty) => {
    const { value } = property;

    const { previous: previousValue } = value;

    return (
      <div className="flex">
        <Badge type={BADGE_TYPES.CANCEL}>
          {displayValue(previousValue)}
        </Badge>
      </div>
    );
  },
  updated: (property: tDataDiffNodeProperty) => {
    const { value } = property;

    const { new: newValue, previous: previousValue } = value;

    return (
      <div className="flex items-center">
        <div className="flex">
          <Tooltip message="Previous value">
            <Badge type={BADGE_TYPES.CANCEL}>
              {displayValue(previousValue)}
            </Badge>
          </Tooltip>
        </div>

        <div>
          <ChevronRightIcon className="h-5 w-5 mr-2" aria-hidden="true" />
        </div>

        <div className="flex">
          <Tooltip message="New value">
            <Badge type={BADGE_TYPES.VALIDATE}>
              {displayValue(newValue)}
            </Badge>
          </Tooltip>
        </div>
      </div>
    );
  },
};
import { BADGE_TYPES, Badge } from "../../../components/badge";
import { DateDisplay } from "../../../components/date-display";
import { getBadgeType, tDataDiffNodeAttributeProperty } from "./data-diff-node";
import { Tooltip } from "../../../components/tooltip";
import { ChevronRightIcon } from "@heroicons/react/24/outline";

export type tDataDiffNodeAttributeProps = {
  property: tDataDiffNodeAttributeProperty,
}

const displayValue = (value: any) => {
  if (typeof value === "boolean") {
    return `${value}`;
  }

  return value;
};

// Display the values
// (only new one for "added", only old ones for "deleted", and previous + new for "updated")
const diffContent: { [key: string]: any; } = {
  added: (property: tDataDiffNodeAttributeProperty) => {
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
  removed: (property: tDataDiffNodeAttributeProperty) => {
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
  updated: (property: tDataDiffNodeAttributeProperty) => {
    const { value } = property;

    const { new: newValue, previous: previousValue } = value;

    return (
      <>
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
      </>
    );
  },
};

export const DataDiffAttributeProperty = (props: tDataDiffNodeAttributeProps) => {
  const { property } = props;

  const {
    type,
    action,
    changed_at,
  } = property;

  return (
    <div className="p-2 bg-gray-100 grid grid-cols-5 gap-4">
      <div className="flex items-center">
        <Badge className="" type={getBadgeType(action)}>
          {action?.toUpperCase()}
        </Badge>
      </div>

      <div className="flex items-center">
        <span className="mr-4">
          {type}
        </span>
      </div>

      <div className="flex items-center">
        {diffContent[action](property)}
      </div>

      <div className="flex items-center">
        {
          changed_at
          && (
            <DateDisplay date={changed_at} hideDefault />
          )
        }
      </div>
    </div>
  );
};
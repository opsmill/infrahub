import { ChevronRightIcon } from "@heroicons/react/24/outline";
import { BADGE_TYPES, Badge } from "../../../components/badge";
import { DateDisplay } from "../../../components/date-display";
import { getBadgeType, tDataDiffNodeAttributeProperty } from "./data-diff-node";
import { Tooltip } from "../../../components/tooltip";

export type tDataDiffNodeAttributeProps = {
  property: tDataDiffNodeAttributeProperty,
}

const displayValue = (value: any) => {
  if (typeof value === "boolean") {
    return `${value}`;
  }

  return value;
};

export const DataDiffAttributeProperty = (props: tDataDiffNodeAttributeProps) => {
  const { property } = props;

  const {
    type,
    action,
    changed_at,
    value
  } = property;

  const { new: newValue, previous } = value;

  return (
    <div className="ml-4 p-2 flex border-l border-gray-200">
      <div className="ml-4">
        <Badge className="mr-4">
          {type}
        </Badge>
      </div>

      <div>
        <Badge className="mr-4" type={getBadgeType(action)}>
          {action?.toUpperCase()}
        </Badge>
      </div>

      <div>

        <Tooltip message="Previous value">
          <Badge type={BADGE_TYPES.CANCEL}>
            {displayValue(previous)}
          </Badge>
        </Tooltip>
      </div>

      <div>
        <ChevronRightIcon className="h-5 w-5 mr-2" aria-hidden="true"/>
      </div>

      <div>

        <Tooltip message="New value">
          <Badge type={BADGE_TYPES.VALIDATE}>
            {displayValue(newValue)}
          </Badge>
        </Tooltip>
      </div>

      <div>
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
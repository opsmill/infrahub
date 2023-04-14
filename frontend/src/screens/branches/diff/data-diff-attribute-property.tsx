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

  // return (
  //   <div className="ml-4 p-2 border-l border-gray-200 flex">
  //     <div className="">
  //       <Badge className="ml-4 mr-4" type={getBadgeType(action)}>
  //         {action?.toUpperCase()}
  //       </Badge>
  //     </div>

  //     <div className="">
  //       <span className="mr-4">
  //         {type}
  //       </span>
  //     </div>

  //     <div className="">
  //       <Tooltip message="Previous value">
  //         <Badge type={BADGE_TYPES.CANCEL}>
  //           {displayValue(previous)}
  //         </Badge>
  //       </Tooltip>
  //     </div>

  //     <div className="">
  //       <Tooltip message="New value">
  //         <Badge type={BADGE_TYPES.VALIDATE}>
  //           {displayValue(newValue)}
  //         </Badge>
  //       </Tooltip>
  //     </div>

  //     <div className="">
  //       {
  //         changed_at
  //         && (
  //           <DateDisplay date={changed_at} hideDefault />
  //         )
  //       }
  //     </div>
  //   </div>
  // );

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

      <div className="flex">
        <Tooltip message="Previous value">
          <Badge type={BADGE_TYPES.CANCEL}>
            {displayValue(previous)}
          </Badge>
        </Tooltip>
      </div>

      <div className="flex">
        <Tooltip message="New value">
          <Badge type={BADGE_TYPES.VALIDATE}>
            {displayValue(newValue)}
          </Badge>
        </Tooltip>
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
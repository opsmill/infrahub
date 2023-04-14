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
    <div className="ml-4 p-2 border-l border-gray-200 flex">
      <div className="">
        <Badge className="ml-4 mr-4" type={getBadgeType(action)}>
          {action?.toUpperCase()}
        </Badge>
      </div>

      <div className="">
        <span className="mr-4">
          {type}
        </span>
      </div>

      <div className="flex">
        <div className="">
          <Tooltip message="Previous value">
            <Badge type={BADGE_TYPES.CANCEL}>
              {displayValue(previous)}
            </Badge>
          </Tooltip>
        </div>

        <div className="">
          <ChevronRightIcon className="h-5 w-5 mr-2" aria-hidden="true"/>
        </div>

        <div className="flex flex-1 justify-start items-center">
          <Tooltip message="New value">
            <Badge type={BADGE_TYPES.VALIDATE}>
              {displayValue(newValue)}
            </Badge>
          </Tooltip>
        </div>
      </div>

      <div className="">
        {
          changed_at
          && (
            <DateDisplay date={changed_at} hideDefault />
          )
        }
      </div>
    </div>
  );

  // return (
  //   <div className="ml-4 p-2 border-l border-gray-200 grid grid-cols-4 gap-4">
  //     <div className="flex items-center justify-center">
  //       <Badge className="ml-4 mr-4" type={getBadgeType(action)}>
  //         {action?.toUpperCase()}
  //       </Badge>
  //     </div>

  //     <div className="flex items-center justify-center">
  //       <span className="mr-4">
  //         {type}
  //       </span>
  //     </div>

  //     <div className="flex">
  //       <div className="flex flex-1 justify-end items-center">
  //         <Tooltip message="Previous value">
  //           <Badge type={BADGE_TYPES.CANCEL}>
  //             {displayValue(previous)}
  //           </Badge>
  //         </Tooltip>
  //       </div>

  //       <div className="flex items-center justify-center">
  //         <ChevronRightIcon className="h-5 w-5 mr-2" aria-hidden="true"/>
  //       </div>

  //       <div className="flex flex-1 justify-start items-center">
  //         <Tooltip message="New value">
  //           <Badge type={BADGE_TYPES.VALIDATE}>
  //             {displayValue(newValue)}
  //           </Badge>
  //         </Tooltip>
  //       </div>
  //     </div>

  //     <div className="flex items-center justify-center">
  //       {
  //         changed_at
  //         && (
  //           <DateDisplay date={changed_at} hideDefault />
  //         )
  //       }
  //     </div>
  //   </div>
  // );
};
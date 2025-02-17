import { EventNodeInterface } from "@/shared/api/graphql/generated/graphql";
import { Icon } from "@iconify-icon/react";
import { BRANCH_EVENTS_MAPPING } from "./branch-event";

export const BranchEvent = (props: EventNodeInterface) => {
  const { event, branch } = props;

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Icon icon="mdi:source-branch" className="text-gray-400" />

        {branch && BRANCH_EVENTS_MAPPING[event] && BRANCH_EVENTS_MAPPING[event](branch)}
      </div>
    </div>
  );
};

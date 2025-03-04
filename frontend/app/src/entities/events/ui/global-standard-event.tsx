import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { EventNodeInterface } from "@/shared/api/graphql/generated/graphql";
import { Icon } from "@iconify-icon/react";
import { STANDARD_EVENTS_MAPPING } from "./standard-event";

const getStandardEventIcon = (event: string) => {
  if (event.includes("schema")) {
    return <Icon icon="mdi:code-json" className="text-gray-400" />;
  }

  return <Icon icon="mdi:calendar-task-outline" className="text-gray-400" />;
};

export const StandardEvent = (props: EventNodeInterface) => {
  const { event, account_id } = props;

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          {getStandardEventIcon(event)}

          {account_id ? (
            <div className="text-black font-semibold">
              <NodeLabel id={account_id} kind="CoreAccount" />
            </div>
          ) : (
            "-"
          )}

          {(STANDARD_EVENTS_MAPPING[event] && STANDARD_EVENTS_MAPPING[event](props)) ?? event}
        </div>
      </div>
    </>
  );
};

import { NodeLabel } from "@/entities/nodes/object/ui/display-label";
import { EventNodeInterface } from "@/shared/api/graphql/generated/graphql";
import { Icon } from "@iconify-icon/react";
import { GROUP_EVENTS_MAPPING } from "./group-event";

export const GroupEvent = (props: EventNodeInterface) => {
  const { event, account_id, primary_node, related_nodes } = props;

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Icon icon="mdi:group" className="text-gray-400" />

          <div className="text-black font-semibold">
            <NodeLabel id={account_id} />
          </div>

          {primary_node?.id &&
            GROUP_EVENTS_MAPPING[event] &&
            GROUP_EVENTS_MAPPING[event](related_nodes, primary_node?.id)}
        </div>
      </div>
    </>
  );
};

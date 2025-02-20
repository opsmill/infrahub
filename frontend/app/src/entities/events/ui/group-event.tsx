import { DisplayLabel } from "@/entities/nodes/object/ui/display-label";
import { EventNodeInterface } from "@/shared/api/graphql/generated/graphql";
import { ReactElement } from "react";

export const GROUP_EVENTS_MAPPING: Record<string, (node: string, group: string) => ReactElement> = {
  "infrahub.group.member_added": (nodeId, groupId) => (
    <div className="flex items-center gap-2">
      added{" "}
      <span className="text-black font-semibold">
        <DisplayLabel id={nodeId} />
      </span>{" "}
      in group{" "}
      <span className="text-black font-semibold">
        <DisplayLabel id={groupId} />
      </span>
    </div>
  ),
  "infrahub.group.member_removed": (nodeId, groupId) => (
    <div className="flex items-center gap-2">
      removed{" "}
      <span className="text-black font-semibold">
        <DisplayLabel id={nodeId} />
      </span>{" "}
      from group{" "}
      <span className="text-black font-semibold">
        <DisplayLabel id={groupId} />
      </span>
    </div>
  ),
};

export const GroupEvent = (props: EventNodeInterface) => {
  const { event, account_id, primary_node, related_node } = props;

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          <div className="font-semibold">
            <DisplayLabel id={account_id} />
          </div>

          <div className="text-gray-500">
            {primary_node?.id &&
              GROUP_EVENTS_MAPPING[event] &&
              GROUP_EVENTS_MAPPING[event](related_node?.id, primary_node?.id)}
          </div>
        </div>
      </div>
    </>
  );
};

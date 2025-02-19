import { DisplayLabel } from "@/entities/nodes/object/ui/display-label";
import { EventNodeInterface } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { Link } from "@/shared/components/ui/link";
import { ReactElement } from "react";

export const GROUP_EVENTS_MAPPING: Record<
  string,
  (nodes: Array<{ id: string; kind: string }>, groupId: string) => ReactElement
> = {
  "infrahub.group.member_added": (nodes, groupId) => (
    <div className="flex items-center gap-2">
      added{" "}
      <div className="flex items-center gap-1 text-black">
        {nodes.map(({ id, kind }) => {
          return (
            <Link key={id} to={constructPath(`/objects/${kind}/${id}`)}>
              <DisplayLabel key={id} id={id} />
            </Link>
          );
        })}
      </div>{" "}
      in group{" "}
      <span className="text-black font-semibold">
        <Link key={groupId} to={constructPath(`/objects/CoreGroup/${groupId}`)}>
          <DisplayLabel key={groupId} id={groupId} kind="CoreGroup" />
        </Link>
      </span>
    </div>
  ),
  "infrahub.group.member_removed": (nodes, groupId) => (
    <div className="flex items-center gap-2">
      removed{" "}
      <div className="flex items-center gap-1 text-black">
        {nodes.map(({ id, kind }) => {
          return (
            <Link key={id} to={constructPath(`/objects/${kind}/${id}`)}>
              <DisplayLabel key={id} id={id} />
            </Link>
          );
        })}
      </div>{" "}
      from group{" "}
      <span className="text-black">
        <Link key={groupId} to={constructPath(`/objects/CoreGroup/${groupId}`)}>
          <DisplayLabel key={groupId} id={groupId} kind="CoreGroup" />
        </Link>
      </span>
    </div>
  ),
};

export const GroupEvent = (props: EventNodeInterface) => {
  const { event, account_id, primary_node, related_nodes } = props;

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
              GROUP_EVENTS_MAPPING[event](related_nodes, primary_node?.id)}
          </div>
        </div>
      </div>
    </>
  );
};

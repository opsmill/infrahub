import { NodeLabel } from "@/entities/nodes/object/ui/display-label";
import { EventNodeInterface } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { Link } from "@/shared/components/ui/link";
import { ReactElement } from "react";

export const STANDARD_EVENTS_MAPPING: Record<
  string,
  (nodes: Array<{ id: string; kind: string }>, primaryNodeId?: string) => ReactElement
> = {
  "infrahub.group.member_added": (nodes, primaryNodeId) => (
    <div className="flex items-center gap-2">
      added{" "}
      <div className="flex items-center gap-1 text-black">
        {nodes.map(({ id, kind }) => {
          return (
            <Link key={id} to={constructPath(`/objects/${kind}/${id}`)}>
              <NodeLabel key={id} id={id} />
            </Link>
          );
        })}
      </div>{" "}
      in group{" "}
      <span className="text-black font-semibold">
        <Link key={primaryNodeId} to={constructPath(`/objects/CoreGroup/${primaryNodeId}`)}>
          <NodeLabel key={primaryNodeId} id={primaryNodeId} kind="CoreGroup" />
        </Link>
      </span>
    </div>
  ),
  "infrahub.group.member_removed": (nodes, primaryNodeId) => (
    <div className="flex items-center gap-2">
      removed{" "}
      <div className="flex items-center gap-1 text-black">
        {nodes.map(({ id, kind }) => {
          return (
            <Link key={id} to={constructPath(`/objects/${kind}/${id}`)}>
              <NodeLabel key={id} id={id} />
            </Link>
          );
        })}
      </div>{" "}
      from group{" "}
      <span className="text-black">
        <Link key={primaryNodeId} to={constructPath(`/objects/CoreGroup/${primaryNodeId}`)}>
          <NodeLabel key={primaryNodeId} id={primaryNodeId} kind="CoreGroup" />
        </Link>
      </span>
    </div>
  ),
  "infrahub.schema.update": () => <div className="flex items-center gap-2">updated the schema</div>,
};

export const StandardEvent = (props: EventNodeInterface) => {
  const { event, account_id, primary_node, related_nodes } = props;

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          <div className="font-semibold">
            <NodeLabel id={account_id} />
          </div>

          <div className="text-gray-500">
            {STANDARD_EVENTS_MAPPING[event] &&
              STANDARD_EVENTS_MAPPING[event](related_nodes, primary_node?.id)}
          </div>
        </div>
      </div>
    </>
  );
};

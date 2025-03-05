import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { EventNodeInterface } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { Link } from "@/shared/components/ui/link";
import { ReactElement } from "react";

export const GROUP_EVENTS_MAPPING: Record<string, (props: EventNodeInterface) => ReactElement> = {
  "infrahub.group.member_added": ({ related_nodes, primary_node }) => {
    return (
      <div className="flex items-center gap-2">
        added{" "}
        <div className="flex items-center gap-1 text-black">
          {related_nodes.slice(0, 5).map(({ id, kind }) => {
            return (
              <Link key={id} to={constructPath(`/objects/${kind}/${id}`)}>
                <NodeLabel key={id} id={id} />
              </Link>
            );
          })}
          {related_nodes.slice(6).length > 0 && (
            <span className="italic text-gray-500">(+{related_nodes.slice(6).length})</span>
          )}
        </div>{" "}
        in group{" "}
        <span className="text-black font-semibold">
          <Link key={primary_node?.id} to={constructPath(`/objects/CoreGroup/${primary_node?.id}`)}>
            <NodeLabel key={primary_node?.id} id={primary_node?.id} kind={primary_node?.kind} />
          </Link>
        </span>
      </div>
    );
  },
  "infrahub.group.member_removed": ({ related_nodes, primary_node }) => {
    return (
      <div className="flex items-center gap-2">
        removed{" "}
        <div className="flex items-center gap-1 text-black">
          {related_nodes.slice(0, 5).map(({ id, kind }) => {
            return (
              <Link key={id} to={constructPath(`/objects/${kind}/${id}`)}>
                <NodeLabel key={id} id={id} />
              </Link>
            );
          })}
          {related_nodes.slice(6).length > 0 && (
            <span className="italic text-gray-500">(+{related_nodes.slice(6).length})</span>
          )}
        </div>{" "}
        from group{" "}
        <span className="text-black">
          <Link key={primary_node?.id} to={constructPath(`/objects/CoreGroup/${primary_node?.id}`)}>
            <NodeLabel key={primary_node?.id} id={primary_node?.id} kind={primary_node?.kind} />
          </Link>
        </span>
      </div>
    );
  },
};

export const GroupEventTitle = (props: EventNodeInterface) => {
  const { event, account_id } = props;

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 text-sm">
          <NodeLabel id={account_id} />

          <div className="text-gray-500">
            {GROUP_EVENTS_MAPPING[event] && GROUP_EVENTS_MAPPING[event](props)}

            {!GROUP_EVENTS_MAPPING[event] && event}
          </div>
        </div>
      </div>
    </>
  );
};

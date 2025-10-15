import type { ReactElement } from "react";

import type { GroupEvent } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { Link } from "@/shared/components/ui/link";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";

export const GROUP_EVENTS_MAPPING: Record<string, (props: GroupEvent) => ReactElement> = {
  "infrahub.group.member_added": (props) => {
    return (
      <div className="flex flex-wrap items-center gap-1 whitespace-nowrap">
        added{" "}
        <div className="flex items-center gap-1 text-black">
          {props.related_nodes.slice(0, 5).map(({ id, kind }) => {
            return (
              <Link key={id} to={constructPath(`/objects/${kind}/${id}`)}>
                <NodeLabel key={id} id={id} branch={props.branch} />
              </Link>
            );
          })}
          {props.related_nodes.slice(6).length > 0 && (
            <span className="text-gray-500 italic">(+{props.related_nodes.slice(6).length})</span>
          )}
        </div>{" "}
        in group{" "}
        <span className="font-semibold text-black">
          <Link
            key={props.primary_node?.id}
            to={constructPath(`/objects/CoreGroup/${props.primary_node?.id}`)}
          >
            <NodeLabel
              key={props.primary_node?.id}
              id={props.primary_node?.id}
              kind={props.primary_node?.kind}
              branch={props.branch}
            />
          </Link>
        </span>
      </div>
    );
  },
  "infrahub.group.member_removed": (props) => {
    return (
      <div className="flex flex-wrap items-center gap-1 whitespace-nowrap">
        removed{" "}
        <div className="flex items-center gap-1 text-black">
          {props.related_nodes.slice(0, 5).map(({ id, kind }) => {
            return (
              <Link key={id} to={constructPath(`/objects/${kind}/${id}`)}>
                <NodeLabel key={id} id={id} branch={props.branch} />
              </Link>
            );
          })}
          {props.related_nodes.slice(6).length > 0 && (
            <span className="text-gray-500 italic">(+{props.related_nodes.slice(6).length})</span>
          )}
        </div>{" "}
        from group{" "}
        <span className="text-black">
          <Link
            key={props.primary_node?.id}
            to={constructPath(`/objects/CoreGroup/${props.primary_node?.id}`)}
          >
            <NodeLabel
              key={props.primary_node?.id}
              id={props.primary_node?.id}
              kind={props.primary_node?.kind}
              branch={props.branch}
            />
          </Link>
        </span>
      </div>
    );
  },
};

export const GroupEventTitle = (props: GroupEvent) => {
  const { event, account_id } = props;

  return (
    <div className="flex flex-wrap items-center gap-1 text-sm">
      {account_id ? <NodeLabel id={account_id} kind="CoreAccount" branch={props.branch} /> : "-"}

      <div className="text-gray-500">
        {GROUP_EVENTS_MAPPING[event] && GROUP_EVENTS_MAPPING[event](props)}

        {!GROUP_EVENTS_MAPPING[event] && event}
      </div>
    </div>
  );
};

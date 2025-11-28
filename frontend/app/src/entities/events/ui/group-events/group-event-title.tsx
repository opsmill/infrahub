import type { ReactElement } from "react";

import type { GroupEvent } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { Link } from "@/shared/components/ui/link";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";

export const GROUP_EVENTS_MAPPING: Record<string, (props: GroupEvent) => ReactElement> = {
  "infrahub.group.member_added": (props) => {
    return (
      <div className="flex min-w-0 items-center gap-1 overflow-hidden">
        <span className="whitespace-nowrap">added</span>
        <div className="flex min-w-0 items-center gap-1 overflow-hidden text-black">
          {props.related_nodes.slice(0, 5).map(({ id, kind }) => {
            return (
              <Link
                key={id}
                to={constructPath(`/objects/${kind}/${id}`)}
                className="max-w-[150px] shrink-0 truncate"
              >
                <NodeLabel key={id} id={id} branch={props.branch} />
              </Link>
            );
          })}
          {props.related_nodes.slice(6).length > 0 && (
            <span className="shrink-0 text-gray-500 italic">
              (+{props.related_nodes.slice(6).length})
            </span>
          )}
        </div>
        <span className="whitespace-nowrap">in group</span>
        <span className="min-w-0 truncate font-semibold text-black">
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
      <div className="flex min-w-0 items-center gap-1 overflow-hidden">
        <span className="whitespace-nowrap">removed</span>
        <div className="flex min-w-0 items-center gap-1 overflow-hidden text-black">
          {props.related_nodes.slice(0, 5).map(({ id, kind }) => {
            return (
              <Link
                key={id}
                to={constructPath(`/objects/${kind}/${id}`)}
                className="max-w-[150px] shrink-0 truncate"
              >
                <NodeLabel key={id} id={id} branch={props.branch} />
              </Link>
            );
          })}
          {props.related_nodes.slice(6).length > 0 && (
            <span className="shrink-0 text-gray-500 italic">
              (+{props.related_nodes.slice(6).length})
            </span>
          )}
        </div>
        <span className="whitespace-nowrap">from group</span>
        <span className="min-w-0 truncate text-black">
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
    <div className="flex w-full min-w-0 items-center gap-1 overflow-hidden text-sm">
      {account_id ? (
        <span className="max-w-[200px] shrink-0 truncate">
          <NodeLabel id={account_id} kind="CoreAccount" branch={props.branch} />
        </span>
      ) : (
        "-"
      )}

      <div className="min-w-0 text-gray-500">
        {GROUP_EVENTS_MAPPING[event] && GROUP_EVENTS_MAPPING[event](props)}

        {!GROUP_EVENTS_MAPPING[event] && event}
      </div>
    </div>
  );
};

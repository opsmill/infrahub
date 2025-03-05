import { ACCOUNT_OBJECT, PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { NODE_EVENTS_MAPPING } from "@/entities/events/ui/node-events/constants";
import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import type { NodeMutatedEvent } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { Link } from "@/shared/components/ui/link";
import { useAtomValue } from "jotai";

export const getLink = ({ kind, id, branch }: { kind: string; id: string; branch: string }) => {
  if (kind === PROPOSED_CHANGES_OBJECT) {
    return constructPath(`/proposed-changes/${id}`);
  }

  if (kind === ACCOUNT_OBJECT) {
    return constructPath("/role-management", [
      {
        name: QSP.BRANCH,
        value: branch,
      },
    ]);
  }

  return constructPath(`/objects/${kind}/${id}`, [
    {
      name: QSP.BRANCH,
      value: branch,
    },
  ]);
};

export const NodeEventTitle = (props: NodeMutatedEvent) => {
  const { event, account_id } = props;
  const schemaLabels = useAtomValue(schemaKindLabelState);

  return (
    <div className="flex items-center gap-2 text-sm">
      <div className="font-semibold">
        <NodeLabel id={account_id} />
      </div>
      <div className="text-gray-500">{NODE_EVENTS_MAPPING[event] ?? "-"}</div>
      <div className="font-semibold">{schemaLabels[props.payload.data.node_kind] ?? "-"}</div>
      {event.includes("deleted") ? (
        <NodeLabel
          id={props.primary_node.id}
          kind={props.primary_node?.kind}
          className="overflow-hidden text-ellipsis whitespace-nowrap"
        />
      ) : (
        <Link
          to={getLink({
            kind: props.primary_node?.kind,
            id: props.primary_node.id,
            branch: props.branch,
          })}
          className="overflow-hidden text-ellipsis"
        >
          <NodeLabel
            id={props.primary_node.id}
            kind={props.primary_node?.kind}
            className="overflow-hidden text-ellipsis whitespace-nowrap"
          />
        </Link>
      )}
    </div>
  );
};

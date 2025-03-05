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

export const NodeEventTitle = ({
  event,
  account_id,
  payload,
  primary_node,
  branch,
}: NodeMutatedEvent) => {
  const schemaLabels = useAtomValue(schemaKindLabelState);

  return (
    <div className="flex items-center gap-1 text-sm">
      <NodeLabel id={account_id} />
      <span className="text-gray-600 whitespace-nowrap">{NODE_EVENTS_MAPPING[event] ?? event}</span>
      <div className="text-gray-600 whitespace-nowrap">
        {schemaLabels[payload.data.node_kind] ?? "-"}
      </div>
      {event.includes("deleted") ? (
        <NodeLabel
          id={primary_node.id}
          kind={primary_node?.kind}
          className="overflow-hidden text-ellipsis whitespace-nowrap"
        />
      ) : (
        <Link
          to={getLink({
            kind: primary_node?.kind,
            id: primary_node.id,
            branch,
          })}
          className="overflow-hidden text-ellipsis"
        >
          <NodeLabel
            id={primary_node.id}
            kind={primary_node?.kind}
            className="overflow-hidden text-ellipsis whitespace-nowrap"
          />
        </Link>
      )}
    </div>
  );
};

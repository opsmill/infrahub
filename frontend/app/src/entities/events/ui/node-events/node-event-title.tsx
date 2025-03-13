import { QSP } from "@/config/qsp";
import { NODE_EVENTS_MAPPING } from "@/entities/events/ui/node-events/constants";
import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { getObjectDetailsUrl2 } from "@/entities/nodes/utils";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import type { NodeMutatedEvent } from "@/shared/api/graphql/generated/graphql";
import { Link } from "@/shared/components/ui/link";
import { useAtomValue } from "jotai";

export const NodeEventTitle = ({
  event,
  account_id,
  payload,
  primary_node,
  branch,
}: NodeMutatedEvent) => {
  const schemaLabels = useAtomValue(schemaKindLabelState);

  return (
    <div className="flex flex-wrap items-center gap-1 text-sm">
      <NodeLabel id={account_id} kind="CoreAccount" branch={branch} />
      <span className="text-gray-600 whitespace-nowrap">{NODE_EVENTS_MAPPING[event] ?? event}</span>
      <div className="text-gray-600 whitespace-nowrap">
        {schemaLabels[payload.data.node_kind] ?? "-"}
      </div>
      {event.includes("deleted") ? (
        <NodeLabel id={primary_node.id} kind={primary_node?.kind} branch={branch} />
      ) : (
        <Link
          to={getObjectDetailsUrl2(primary_node?.kind, primary_node.id, [
            { name: QSP.BRANCH, value: branch },
          ])}
        >
          <NodeLabel id={primary_node.id} kind={primary_node?.kind} branch={branch} />
        </Link>
      )}
    </div>
  );
};

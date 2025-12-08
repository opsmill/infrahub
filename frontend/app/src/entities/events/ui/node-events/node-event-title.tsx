import { useAtomValue } from "jotai";

import type { NodeMutatedEvent } from "@/shared/api/graphql/generated/graphql";
import { Link } from "@/shared/components/ui/link";
import { QSP } from "@/shared/config/qsp";

import { NODE_EVENTS_MAPPING } from "@/entities/events/ui/node-events/constants";
import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";

const NodeEventTitleContent = ({ primary_node, event, branch }: NodeMutatedEvent) => {
  if (!primary_node?.id || !primary_node?.kind) {
    return "-";
  }

  if (event.includes("deleted")) {
    return <NodeLabel id={primary_node.id} kind={primary_node.kind} branch={branch} />;
  }

  return (
    <Link
      to={getObjectDetailsUrl(primary_node.kind, primary_node.id, [
        { name: QSP.BRANCH, value: branch },
      ])}
      className="min-w-0 flex-1 cursor-pointer truncate rounded-md"
    >
      <NodeLabel id={primary_node.id} kind={primary_node.kind} branch={branch} />
    </Link>
  );
};

export const NodeEventTitle = (props: NodeMutatedEvent) => {
  const schemaLabels = useAtomValue(schemaKindLabelState);

  const { event, account_id, payload, branch } = props;

  return (
    <div className="flex w-full min-w-0 items-center gap-1 overflow-hidden text-sm">
      {account_id ? (
        <span className="max-w-[200px] shrink-0 truncate">
          <NodeLabel id={account_id} kind="CoreAccount" branch={branch} />
        </span>
      ) : (
        "-"
      )}

      <span className="whitespace-nowrap text-gray-600 dark:text-gray-400">
        {NODE_EVENTS_MAPPING[event] ?? event}
      </span>

      <div className="whitespace-nowrap text-gray-600 dark:text-gray-400">
        {schemaLabels[payload.data.node_kind] ?? "-"}
      </div>

      <NodeEventTitleContent {...props} />
    </div>
  );
};

import { ACCOUNT_OBJECT, PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import { NodeMutatedEvent } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { Link } from "@/shared/components/ui/link";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";

export const NODE_EVENTS_MAPPING: Record<string, string> = {
  "infrahub.node.created": "created",
  "infrahub.node.updated": "updated",
  "infrahub.node.deleted": "deleted",
};

export const EventAttributes = ({ attributes }: Pick<NodeMutatedEvent, "attributes">) => {
  return (
    <div className="flex flex-col gap-2 text-xs">
      {attributes.map(({ action, name, value, value_previous }) => {
        return (
          <div className="grid grid-cols-2 gap-2 items-center" key={`${action}_${name}`}>
            <div className="font-medium text-gray-500 flex items-center h-8">{name}</div>

            <div className="flex items-center gap-4">
              <div className="text-gray-400">{value_previous ?? "Ø"}</div>

              <Icon icon={"mdi:chevron-right"} className="text-custom-blue-500" />

              <div>{value ?? "Ø"}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

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

export const NodeEvent = (props: NodeMutatedEvent) => {
  const { event, account_id } = props;
  const schemaLabels = useAtomValue(schemaKindLabelState);

  return (
    <>
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
    </>
  );
};

import { QSP } from "@/config/qsp";
import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { NodeMutatedEvent } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { Link } from "@/shared/components/ui/link";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { NODE_EVENTS_MAPPING } from "./node-event";

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

export const NodeEvent = (props: NodeMutatedEvent) => {
  const { event, account_id } = props;
  const schemaLabels = useAtomValue(schemaKindLabelState);
  const { schema } = useSchema(props.payload.data.node_kind);

  return (
    <div className="flex items-center gap-2 text-sm">
      <Icon icon={schema?.icon ?? "mdi:cube-outline"} className="text-gray-400" />

      <NodeLabel
        id={account_id}
        className="overflow-hidden text-ellipsis whitespace-nowrap font-semibold"
      />

      <div className="text-gray-500">{NODE_EVENTS_MAPPING[event] ?? "-"}</div>

      <div className="font-semibold whitespace-nowrap">
        {schemaLabels[props.payload.data.node_kind] ?? "-"}
      </div>

      <Link
        to={constructPath(
          `/objects/${props.payload.data.node_kind}/${props.payload.data.node_id}`,
          [
            {
              name: QSP.BRANCH,
              value: props.branch,
            },
          ]
        )}
        className="overflow-hidden text-ellipsis"
      >
        <NodeLabel
          id={props.primary_node.id}
          kind={props.primary_node?.kind}
          className="overflow-hidden text-ellipsis whitespace-nowrap"
        />
      </Link>
    </div>
  );
};

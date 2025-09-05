import { Icon } from "@iconify-icon/react";
import React from "react";

import type { NodeMutatedEvent } from "@/shared/api/graphql/generated/graphql";
import { Card } from "@/shared/components/ui/card";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";

const ActionMapping = {
  ADDED: <Icon icon={"mdi:add"} className="text-green-500" />,
  REMOVED: <Icon icon={"mdi:minus"} className="text-red-500" />,
  UPDATED: <Icon icon={"mdi:exchange"} className="text-custom-blue-500" />,
  UNCHANGED: <Icon icon={"mdi:dot"} className="text-gray-400" />,
};

export const EventRelationships = ({ relationships }: Pick<NodeMutatedEvent, "relationships">) => {
  if (relationships.length === 0) return null;

  return (
    <Card className="flex flex-col gap-1.5 bg-zinc-50 text-xs">
      {relationships.map(({ action, name, peer }) => {
        return (
          <React.Fragment key={`${peer.id}`}>
            <div className="flex items-center gap-2 overflow-hidden">
              <div className="truncate text-left text-gray-600">{name}</div>

              {ActionMapping[action] ?? "-"}

              <NodeLabel id={peer.id} kind={peer.kind} />
            </div>
          </React.Fragment>
        );
      })}
    </Card>
  );
};

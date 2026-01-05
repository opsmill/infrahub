import { XIcon } from "lucide-react";
import { Button as AriaButton } from "react-aria-components";

import { GroupItem } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/group-item";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";

export interface SelectedGroupItemProps {
  group: RelationshipNode;
  onRemove: (group: RelationshipNode) => void;
}

export function SelectedGroupItem({ group, onRemove }: SelectedGroupItemProps) {
  const label = getNodeLabel(group);

  return (
    <GroupItem group={group}>
      <AriaButton
        className="cursor-pointer rounded-full p-0.5 text-stone-400 hover:bg-stone-200"
        aria-label={`Remove from group ${label}`}
        onPress={() => onRemove(group)}
      >
        <XIcon className="size-3" />
      </AriaButton>
    </GroupItem>
  );
}

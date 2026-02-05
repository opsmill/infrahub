import { ListBox } from "react-aria-components";

import { Button } from "@/shared/components/ui/button";

import {
  GroupPanelBody,
  GroupPanelFooter,
  GroupPanelHeader,
} from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/group-panel";
import { SelectedGroupItem } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/selected-group-item";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";

export interface SelectedGroupsPanelProps {
  selectedGroups: RelationshipNode[];
  onRemoveGroup: (group: RelationshipNode) => void;
  onValidate: () => void;
}

export function SelectedGroupsPanel({
  selectedGroups,
  onRemoveGroup,
  onValidate,
}: SelectedGroupsPanelProps) {
  return (
    <div
      className="flex max-h-[12rem] min-w-[15rem] max-w-sm flex-col border-gray-200 border-l"
      data-testid="selected-groups-panel"
    >
      <GroupPanelHeader>Selected groups</GroupPanelHeader>

      <GroupPanelBody>
        <ListBox
          items={selectedGroups}
          aria-label="Selected groups"
          className="flex flex-col items-start gap-1 p-2"
        >
          {(group) => <SelectedGroupItem group={group} onRemove={onRemoveGroup} />}
        </ListBox>
      </GroupPanelBody>

      <GroupPanelFooter>
        <Button size="xs" onClick={onValidate}>
          Validate
        </Button>
      </GroupPanelFooter>
    </div>
  );
}

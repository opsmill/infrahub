import {
  GroupPanelBody,
  GroupPanelFooter,
  GroupPanelHeader,
} from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/group-panel";
import { SelectedGroupItem } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/selected-group-item";
import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ListBox } from "react-aria-components";

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
      className="border-l border-gray-200 min-w-[15rem] max-w-sm max-h-[12rem] flex flex-col"
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

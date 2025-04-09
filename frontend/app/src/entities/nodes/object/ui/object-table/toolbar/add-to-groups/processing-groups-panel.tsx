import { ProcessingGroupItem } from "@/entities/nodes/object/ui/object-table/toolbar/add-to-groups/processing-group-item";
import {
  GroupPanelBody,
  GroupPanelFooter,
  GroupPanelHeader,
} from "@/entities/nodes/object/ui/object-table/toolbar/group-panel";
import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { NodeObject } from "@/entities/nodes/types";
import { Button } from "@/shared/components/buttons/button-primitive";
import { pluralize } from "@/shared/utils/string";
import React from "react";
import { ListBox } from "react-aria-components";

export interface ProcessingGroupsPanelProps {
  selectedGroups: RelationshipNode[];
  selectedRows: NodeObject[];
  onSuccess: () => void;
}

export function ProcessingGroupsPanel({
  selectedGroups,
  selectedRows,
  onSuccess,
}: ProcessingGroupsPanelProps) {
  const [successCount, setSuccessCount] = React.useState(0);

  return (
    <div className="border-l min-w-[15rem] max-w-sm max-h-[12rem] flex flex-col">
      <GroupPanelHeader>
        {successCount} / {pluralize(selectedGroups.length, "group")} updated successfully
      </GroupPanelHeader>

      <GroupPanelBody>
        <ListBox
          items={selectedGroups}
          aria-label="Processing groups"
          className="flex flex-col items-start gap-1 p-2"
        >
          {(group) => (
            <ProcessingGroupItem
              group={group}
              selectedRows={selectedRows}
              onSuccess={() => setSuccessCount((prev) => prev + 1)}
              key={group.id}
            />
          )}
        </ListBox>
      </GroupPanelBody>

      <GroupPanelFooter>
        <Button size="xs" onClick={onSuccess}>
          Close
        </Button>
      </GroupPanelFooter>
    </div>
  );
}

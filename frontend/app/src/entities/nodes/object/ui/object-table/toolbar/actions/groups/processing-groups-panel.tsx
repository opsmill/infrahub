import React from "react";
import { ListBox } from "react-aria-components";

import { Button } from "@/shared/components/buttons/button-primitive";
import { pluralize } from "@/shared/utils/string";

import {
  GroupPanelBody,
  GroupPanelFooter,
  GroupPanelHeader,
} from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/group-panel";
import {
  ProcessingGroupItem,
  type ProcessingGroupItemProps,
} from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/processing-group-item";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";

export interface ProcessingGroupsPanelProps extends Omit<ProcessingGroupItemProps, "group"> {
  selectedGroups: RelationshipNode[];
}

export function ProcessingGroupsPanel({
  selectedGroups,
  mutationFn,
  onSuccess,
}: ProcessingGroupsPanelProps) {
  const [successCount, setSuccessCount] = React.useState(0);

  return (
    <div
      className="flex max-h-[12rem] min-w-[15rem] max-w-sm flex-col"
      data-testid="processing-groups-panel"
    >
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
              key={group.id}
              group={group}
              mutationFn={mutationFn}
              onSuccess={() => setSuccessCount((prev) => prev + 1)}
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

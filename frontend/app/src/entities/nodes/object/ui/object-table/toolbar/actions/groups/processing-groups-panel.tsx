import { Button } from "@infrahub/ui";
import React from "react";
import { ListBox } from "react-aria-components";

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
  onClose: () => void;
}

export function ProcessingGroupsPanel({
  selectedGroups,
  mutationFn,
  onSuccess,
  onClose,
}: ProcessingGroupsPanelProps) {
  const [successCount, setSuccessCount] = React.useState(0);
  const allDone = selectedGroups.length > 0 && successCount === selectedGroups.length;

  React.useEffect(() => {
    if (allDone) {
      onSuccess()?.catch(console.error);
    }
  }, [allDone]);

  return (
    <div className="flex max-h-48 min-w-60 max-w-sm flex-col" data-testid="processing-groups-panel">
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
        <Button size="xs" onPress={onClose}>
          Close
        </Button>
      </GroupPanelFooter>
    </div>
  );
}

import React from "react";

import {
  ProcessingGroupsPanel,
  type ProcessingGroupsPanelProps,
} from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/processing-groups-panel";
import { SelectedGroupsPanel } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/selected-groups-panel";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import {
  RelationshipComboboxList,
  type RelationshipComboboxListProps,
} from "@/entities/nodes/relationships/ui/relationship-combobox-list";

export interface BulkMutateGroupsProps extends Omit<ProcessingGroupsPanelProps, "selectedGroups"> {
  groupsQueryFilter?: RelationshipComboboxListProps["filterQuery"];
}

export function BulkMutateGroups({
  mutationFn,
  onSuccess,
  groupsQueryFilter,
}: BulkMutateGroupsProps) {
  const [selectedGroups, setSelectedGroups] = React.useState<RelationshipNode[]>([]);
  const [isProcessing, setIsProcessing] = React.useState(false);

  if (isProcessing) {
    return (
      <ProcessingGroupsPanel
        selectedGroups={selectedGroups}
        mutationFn={mutationFn}
        onSuccess={onSuccess}
      />
    );
  }

  return (
    <div className="flex">
      <RelationshipComboboxList
        autoFocus
        peer="CoreGroup"
        onSelect={(group) => {
          setSelectedGroups((prev) => [...prev, group]);
        }}
        filterItem={(node) => !selectedGroups.some((v) => v.id === node.id)}
        className="max-h-[12rem] max-w-xs"
        data-testid="group-selector"
        filterQuery={groupsQueryFilter}
      />

      {selectedGroups.length > 0 && (
        <SelectedGroupsPanel
          selectedGroups={selectedGroups}
          onRemoveGroup={(group) => {
            setSelectedGroups((prev) => prev.filter((g) => g.id !== group.id));
          }}
          onValidate={() => setIsProcessing(true)}
        />
      )}
    </div>
  );
}

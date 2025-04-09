import { ProcessingGroupsPanel } from "@/entities/nodes/object/ui/object-table/toolbar/add-to-groups/processing-groups-panel";
import { SelectedGroupsPanel } from "@/entities/nodes/object/ui/object-table/toolbar/add-to-groups/selected-groups-panel";
import { ToolbarButton } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import { NodeObject } from "@/entities/nodes/types";
import { Popover, PopoverDialog } from "@/shared/components/aria/popover";
import React from "react";
import { DialogTrigger } from "react-aria-components";

export interface ToolbarAddToGroupActionProps {
  selectedRows: Array<NodeObject>;
}

export function ToolbarAddToGroupsAction({ selectedRows }: ToolbarAddToGroupActionProps) {
  return (
    <DialogTrigger>
      <ToolbarButton>Add to groups</ToolbarButton>

      <Popover placement="top start">
        <PopoverDialog className="p-0">
          {({ close }) => <BulkAddToGroups selectedRows={selectedRows} onSuccess={close} />}
        </PopoverDialog>
      </Popover>
    </DialogTrigger>
  );
}

export function BulkAddToGroups({
  selectedRows,
  onSuccess,
}: ToolbarAddToGroupActionProps & { onSuccess: () => void }) {
  const [selectedGroups, setSelectedGroups] = React.useState<RelationshipNode[]>([]);
  const [isProcessing, setIsProcessing] = React.useState(false);

  if (isProcessing) {
    return (
      <ProcessingGroupsPanel
        selectedGroups={selectedGroups}
        selectedRows={selectedRows}
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

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import { NodeObject } from "@/entities/nodes/types";
import { Popover } from "@/shared/components/aria/popover";
import { XIcon } from "lucide-react";
import React from "react";
import {
  Button as AriaButton,
  Dialog,
  DialogTrigger,
  ListBox,
  ListBoxItem,
} from "react-aria-components";
import { Button } from "@/shared/components/buttons/button-primitive";
import { useAddRelationships } from "@/entities/nodes/relationships/domain/add-relationships/add-relationships.mutation";

export interface ToolbarAddToGroupActionProps {
  selectedRows: Array<NodeObject>;
}

export function ToolbarAddToGroupsAction({ selectedRows }: ToolbarAddToGroupActionProps) {
  return (
    <DialogTrigger>
      <AriaButton className="border border-neutral-200 bg-white rounded-lg px-2 py-1 hover:bg-neutral-50">
        Add to groups
      </AriaButton>

      <Popover placement="top start">
        <Dialog>
          {({ close }) => <BulkAddToGroups selectedRows={selectedRows} onSuccess={close} />}
        </Dialog>
      </Popover>
    </DialogTrigger>
  );
}

function BulkAddToGroups({
  selectedRows,
  onSuccess,
}: ToolbarAddToGroupActionProps & { onSuccess: (groups: RelationshipNode[]) => void }) {
  const [selectedGroups, setSelectedGroups] = React.useState<RelationshipNode[]>([]);

  return (
    <div className="flex">
      <GroupSelector
        selectedGroups={selectedGroups}
        onSelectGroup={(group) => {
          setSelectedGroups((prev) => [...prev, group]);
        }}
      />

      {selectedGroups.length > 0 && (
        <SelectedGroupsPanel
          selectedGroups={selectedGroups}
          selectedRows={selectedRows}
          onRemoveGroup={(group) => {
            setSelectedGroups((prev) => prev.filter((g) => g.id !== group.id));
          }}
          onSuccess={onSuccess}
        />
      )}
    </div>
  );
}

interface GroupSelectorProps {
  selectedGroups: RelationshipNode[];
  onSelectGroup: (group: RelationshipNode) => void;
}

function GroupSelector({ selectedGroups, onSelectGroup }: GroupSelectorProps) {
  return (
    <RelationshipComboboxList
      autoFocus
      peer="CoreGroup"
      onSelect={onSelectGroup}
      filterItem={(node) => !selectedGroups.some((v) => v.id === node.id)}
      className="max-h-[12rem] max-w-xs"
    />
  );
}

interface SelectedGroupsPanelProps {
  selectedGroups: RelationshipNode[];
  selectedRows: Array<NodeObject>;
  onRemoveGroup: (group: RelationshipNode) => void;
  onSuccess: (groups: RelationshipNode[]) => void;
}

function SelectedGroupsPanel({
  selectedGroups,
  selectedRows,
  onRemoveGroup,
  onSuccess,
}: SelectedGroupsPanelProps) {
  const { mutate: addRelationships, isPending } = useAddRelationships();

  const handleValidate = () => {
    selectedGroups.forEach((group) => {
      addRelationships({
        objectId: group.id,
        relationshipName: "members",
        relationshipIds: selectedRows.map((row) => row.id),
      });
    });

    onSuccess(selectedGroups);
  };

  return (
    <div className="border-l min-w-[15rem] max-w-sm max-h-[12rem] flex flex-col">
      <h3 className="font-medium text-xs border-b h-10 shrink-0 flex items-center p-2 text-neutral-600">
        Selected groups
      </h3>

      <div className="grow overflow-auto">
        <ListBox items={selectedGroups} className="flex flex-col items-start gap-1 p-2">
          {(group) => (
            <AddedGroupItem group={group} selectedRows={selectedRows} onRemove={onRemoveGroup} />
          )}
        </ListBox>
      </div>

      <div className="shrink-0 p-1 text-center border-t">
        <Button size="xs" onClick={handleValidate} disabled={isPending}>
          {isPending ? "Processing..." : "Validate"}
        </Button>
      </div>
    </div>
  );
}

function AddedGroupItem({
  group,
  onRemove,
}: ToolbarAddToGroupActionProps & {
  group: RelationshipNode;
  onRemove: (group: RelationshipNode) => void;
}) {
  const label = getNodeLabel(group);

  return (
    <ListBoxItem className="inline-flex items-center px-1 py-0.5 text-sm bg-stone-100 rounded-full overflow-hidden max-w-full">
      <span className="truncate px-1.5">{label}</span>
      <AriaButton
        className="cursor-pointer text-stone-400 p-0.5 hover:bg-stone-200 rounded-full"
        aria-label={`Remove from group ${label}`}
        onPress={() => onRemove(group)}
      >
        <XIcon className="size-3" />
      </AriaButton>
    </ListBoxItem>
  );
}

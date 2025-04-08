import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { useAddRelationships } from "@/entities/nodes/relationships/domain/add-relationships/add-relationships.mutation";
import { useRemoveRelationships } from "@/entities/nodes/relationships/domain/remove-relationships/remove-relationships.mutation";
import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import { NodeObject } from "@/entities/nodes/types";
import { Popover } from "@/shared/components/aria/popover";
import { Spinner } from "@/shared/components/ui/spinner";
import { XIcon } from "lucide-react";
import React, { useEffect } from "react";
import {
  Button as AriaButton,
  Button,
  DialogTrigger,
  ListBox,
  ListBoxItem,
} from "react-aria-components";

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
        <BulkAddToGroups selectedRows={selectedRows} />
      </Popover>
    </DialogTrigger>
  );
}

function BulkAddToGroups({ selectedRows }: ToolbarAddToGroupActionProps) {
  const [selectedGroups, setSelectedGroups] = React.useState<RelationshipNode[]>([]);

  return (
    <div className="flex">
      <RelationshipComboboxList
        peer="CoreGroup"
        onSelect={(group) => {
          setSelectedGroups((prev) => [...prev, group]);
        }}
        filterItem={(node) => !selectedGroups.some((v) => v.id === node.id)}
        className="max-h-[12rem] max-w-xs"
      />

      {selectedGroups.length > 0 && (
        <div className="border-l max-w-sm max-h-[12rem] flex flex-col">
          <h3 className="font-medium text-xs border-b h-10 shrink-0 flex items-center p-2 text-neutral-600">
            Selected groups
          </h3>
          <div className="grow overflow-auto">
            <ListBox items={selectedGroups} className="flex flex-col items-start gap-1 p-2">
              {(group) => (
                <AddedGroupItem
                  group={group}
                  selectedRows={selectedRows}
                  onRemove={(group) => {
                    setSelectedGroups((prev) => prev.filter((g) => g.id !== group.id));
                  }}
                />
              )}
            </ListBox>
          </div>
        </div>
      )}
    </div>
  );
}

function AddedGroupItem({
  group,
  selectedRows,
  onRemove,
}: ToolbarAddToGroupActionProps & {
  group: RelationshipNode;
  onRemove: (group: RelationshipNode) => void;
}) {
  const { mutate: addRelationships, isPending: isPendingAdd } = useAddRelationships();
  const { mutate: removeRelationships, isPending: isPendingRemove } = useRemoveRelationships();

  useEffect(() => {
    addRelationships({
      objectId: group.id,
      relationshipName: "members",
      relationshipIds: selectedRows.map((row) => row.id),
    });
  }, []);

  const label = getNodeLabel(group);
  const GroupItem = ({ children }: { children: React.ReactNode }) => (
    <ListBoxItem className="inline-flex items-center px-1 py-0.5 text-sm bg-stone-100 rounded-full overflow-hidden max-w-full">
      <span className="truncate px-1.5">{label}</span>
      {children}
    </ListBoxItem>
  );

  if (isPendingAdd || isPendingRemove) {
    return (
      <GroupItem>
        <Spinner />
      </GroupItem>
    );
  }

  return (
    <GroupItem>
      <Button
        className="cursor-pointer text-stone-400 p-0.5 hover:bg-stone-200 rounded-full"
        aria-label={`Remove from group ${label}`}
        onPress={() => {
          removeRelationships(
            {
              objectId: group.id,
              relationshipName: "members",
              relationshipIds: selectedRows.map((row) => row.id),
            },
            {
              onSuccess: () => onRemove(group),
            }
          );
        }}
      >
        <XIcon className="size-3" />
      </Button>
    </GroupItem>
  );
}

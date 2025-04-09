import { useAddRelationships } from "@/entities/nodes/relationships/domain/add-relationships/add-relationships.mutation";
import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { NodeObject } from "@/entities/nodes/types";
import { Spinner } from "@/shared/components/ui/spinner";
import { CheckIcon, RefreshCwIcon, TriangleAlertIcon } from "lucide-react";
import React from "react";

import { GroupItem } from "@/entities/nodes/object/ui/object-table/toolbar/add-to-groups/group-item";

export interface ProcessingGroupItemProps {
  group: RelationshipNode;
  selectedRows: NodeObject[];
  onSuccess: () => void;
}

export function ProcessingGroupItem({ group, selectedRows, onSuccess }: ProcessingGroupItemProps) {
  const { mutate: addRelationships, isPending, error } = useAddRelationships();

  const handleProcessing = () => {
    addRelationships(
      {
        objectId: group.id,
        relationshipName: "members",
        relationshipIds: selectedRows.map((row) => row.id),
      },
      {
        onSuccess,
      }
    );
  };

  React.useEffect(() => {
    handleProcessing();
  }, []);

  if (isPending) {
    return (
      <GroupItem group={group}>
        <Spinner />
      </GroupItem>
    );
  }

  if (error) {
    return (
      <GroupItem group={group} className="group">
        <TriangleAlertIcon className="text-red-500 size-4 group-hover:hidden" />
        <RefreshCwIcon
          className="text-red-500 size-4 hidden group-hover:block cursor-pointer"
          onClick={() => handleProcessing()}
        />
      </GroupItem>
    );
  }

  return (
    <GroupItem group={group}>
      <div className="bg-green-200 rounded-full p-0.5">
        <CheckIcon className="size-3 text-gray-800" />
      </div>
    </GroupItem>
  );
}

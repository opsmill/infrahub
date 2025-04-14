import { GroupItem } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/group-item";
import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { Spinner } from "@/shared/components/ui/spinner";
import { useMutation } from "@tanstack/react-query";
import { CheckIcon, RefreshCwIcon, TriangleAlertIcon } from "lucide-react";
import React from "react";

export interface ProcessingGroupItemProps {
  group: RelationshipNode;
  mutationFn: (group: RelationshipNode) => Promise<void>;
  onSuccess: () => void;
}

export function ProcessingGroupItem({ group, mutationFn, onSuccess }: ProcessingGroupItemProps) {
  const { mutate, isPending, error } = useMutation({
    mutationFn,
    onSuccess,
  });

  const handleProcessing = () => {
    mutate(group);
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

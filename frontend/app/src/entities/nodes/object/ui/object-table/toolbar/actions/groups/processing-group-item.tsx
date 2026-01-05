import { useMutation } from "@tanstack/react-query";
import { CheckIcon, RefreshCwIcon, TriangleAlertIcon } from "lucide-react";
import React from "react";

import { Spinner } from "@/shared/components/ui/spinner";

import { GroupItem } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/group-item";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";

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
        <TriangleAlertIcon className="size-4 text-red-500 group-hover:hidden" />
        <RefreshCwIcon
          className="hidden size-4 cursor-pointer text-red-500 group-hover:block"
          onClick={() => handleProcessing()}
        />
      </GroupItem>
    );
  }

  return (
    <GroupItem group={group}>
      <div className="rounded-full bg-green-200 p-0.5">
        <CheckIcon className="size-3 text-gray-800" />
      </div>
    </GroupItem>
  );
}

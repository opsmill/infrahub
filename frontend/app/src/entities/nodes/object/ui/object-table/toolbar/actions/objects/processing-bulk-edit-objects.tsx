import { useMutationState } from "@tanstack/react-query";
import React from "react";

import { queryClient } from "@/shared/api/rest/client";
import { pluralize } from "@/shared/utils/string";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { UpdateObjectParams } from "@/entities/nodes/object/domain/update-object";
import { UPDATE_OBJECT_MUTATION_KEY } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import {
  GroupCard,
  GroupPanelBody,
  GroupPanelHeader,
} from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/group-panel";
import { ProcessingMutateObject } from "@/entities/nodes/object/ui/object-table/toolbar/actions/objects/processing-mutate-object";
import type { NodeCore } from "@/entities/nodes/types";

interface ProcessingBulkEditObjectsProps {
  selectedRows: Array<NodeCore>;
  payload: UpdateObjectParams["data"];
}

export function ProcessingBulkEditObjects({
  selectedRows,
  payload,
}: ProcessingBulkEditObjectsProps) {
  const updateObjectMutationPending = useMutationState({
    filters: {
      mutationKey: UPDATE_OBJECT_MUTATION_KEY,
      status: "pending",
    },
    select: (mutation) => mutation.state.status,
  });

  const [successCount, setSuccessCount] = React.useState(0);

  React.useEffect(() => {
    if (successCount > 0 && updateObjectMutationPending.length === 0) {
      queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    }
  }, [successCount, updateObjectMutationPending.length]);

  return (
    <GroupCard>
      <GroupPanelHeader>
        {successCount} / {pluralize(selectedRows.length, "object")} updated successfully
      </GroupPanelHeader>
      <GroupPanelBody className="flex flex-col gap-2 p-2">
        {selectedRows.map((node) => {
          return (
            <ProcessingMutateObject
              key={node.id}
              node={node}
              payload={payload}
              onSuccess={() => setSuccessCount((prev) => prev + 1)}
            />
          );
        })}
      </GroupPanelBody>
    </GroupCard>
  );
}

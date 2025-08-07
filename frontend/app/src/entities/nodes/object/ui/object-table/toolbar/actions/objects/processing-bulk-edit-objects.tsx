import { UpdateObjectParams } from "@/entities/nodes/object/domain/update-object";
import {
  GroupCard,
  GroupPanelBody,
  GroupPanelHeader,
} from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/group-panel";
import { ProcessingMutateObject } from "@/entities/nodes/object/ui/object-table/toolbar/actions/objects/processing-mutate-object";
import { NodeCore } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";
import { pluralize } from "@/shared/utils/string";
import React from "react";

interface ProcessingBulkEditObjectsProps {
  selectedRows: Array<NodeCore>;
  schema: ModelSchema;
  payload?: UpdateObjectParams["data"];
}

export function ProcessingBulkEditObjects({
  schema,
  selectedRows,
  payload,
}: ProcessingBulkEditObjectsProps) {
  const [successCount, setSuccessCount] = React.useState(0);

  return (
    <GroupCard>
      <GroupPanelHeader>
        {successCount} / {pluralize(selectedRows.length, "object")} updated successfully
      </GroupPanelHeader>
      <GroupPanelBody className="flex flex-col gap-2 p-2">
        {selectedRows.map((node) => {
          return (
            <ProcessingMutateObject
              schema={schema}
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

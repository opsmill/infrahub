import { UpdateObjectParams } from "@/entities/nodes/object/domain/update-object";
import {
  GroupCard,
  GroupPanelBody,
  GroupPanelHeader,
} from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/group-panel";
import { ProcessingBulkEditObjects } from "@/entities/nodes/object/ui/object-table/toolbar/actions/objects/processing-bulk-edit-objects";
import { NodeCard } from "@/entities/nodes/object/ui/object-table/toolbar/actions/objects/processing-mutate-object";
import { NodeCore } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";
import { NodeForm } from "@/shared/components/form/node-form";
import { getUpdateMutationFromFormData } from "@/shared/components/form/utils/mutations/getUpdateMutationFromFormData";
import { pluralize } from "@/shared/utils/string";
import React from "react";

export interface BulkEditObjectsProps {
  selectedRows: Array<NodeCore>;
  schema: ModelSchema;
}

export function BulkEditObjects({ schema, selectedRows }: BulkEditObjectsProps) {
  const [payload, setPayload] = React.useState<UpdateObjectParams["data"]>();

  if (payload) {
    return (
      <ProcessingBulkEditObjects schema={schema} selectedRows={selectedRows} payload={payload} />
    );
  }

  return (
    <div className="flex items-end gap-2">
      <GroupCard>
        <GroupPanelHeader>Editing {pluralize(selectedRows.length, "object")}</GroupPanelHeader>
        <GroupPanelBody className="flex flex-col gap-2 p-2">
          {selectedRows.map((row) => {
            return (
              <NodeCard key={row.id} node={row}>
                Waiting for changes...
              </NodeCard>
            );
          })}
        </GroupPanelBody>
      </GroupCard>

      <GroupCard className="w-100">
        <GroupPanelHeader>Specify changes</GroupPanelHeader>
        <GroupPanelBody>
          <NodeForm
            isFilterForm
            isUpdate
            schema={schema}
            onSubmit={({ fields, formData }) => {
              const updatedObject = getUpdateMutationFromFormData({ formData, fields });
              const isObjectUpdated = Object.keys(updatedObject).length > 0;
              if (isObjectUpdated) {
                setPayload(updatedObject);
              }
            }}
          />
        </GroupPanelBody>
      </GroupCard>
    </div>
  );
}

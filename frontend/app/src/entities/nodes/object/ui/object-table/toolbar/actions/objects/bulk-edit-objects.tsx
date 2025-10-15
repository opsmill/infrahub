import React from "react";

import { NodeForm } from "@/shared/components/form/node-form";
import { getUpdateMutationFromFormData } from "@/shared/components/form/utils/mutations/getUpdateMutationFromFormData";
import { pluralize } from "@/shared/utils/string";

import type { UpdateObjectParams } from "@/entities/nodes/object/domain/update-object";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import {
  GroupCard,
  GroupPanelBody,
  GroupPanelHeader,
} from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/group-panel";
import { ProcessingBulkEditObjects } from "@/entities/nodes/object/ui/object-table/toolbar/actions/objects/processing-bulk-edit-objects";
import { NodeCard } from "@/entities/nodes/object/ui/object-table/toolbar/actions/objects/processing-mutate-object";
import type { NodeCore } from "@/entities/nodes/types";

export interface BulkEditObjectsProps {
  selectedRows: Array<NodeCore>;
}

export function BulkEditObjects({ selectedRows }: BulkEditObjectsProps) {
  const { selectedSchema } = useObjectTableContext();
  const [payload, setPayload] = React.useState<UpdateObjectParams["data"]>();

  if (payload) {
    return <ProcessingBulkEditObjects selectedRows={selectedRows} payload={payload} />;
  }

  return (
    <div className="relative">
      <GroupCard>
        <GroupPanelHeader>
          {pluralize(selectedRows.length, "object")} selected for editing
        </GroupPanelHeader>
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

      <GroupCard className="absolute bottom-0 left-[calc(100%+0.5rem)] w-100">
        <GroupPanelHeader>Set bulk changes</GroupPanelHeader>
        <GroupPanelBody>
          <NodeForm
            isBulkUpdate
            schema={selectedSchema}
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

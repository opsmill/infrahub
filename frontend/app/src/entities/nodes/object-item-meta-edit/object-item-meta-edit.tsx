import { toast } from "react-toastify";
import { mapValues } from "remeda";

import { queryClient } from "@/shared/api/rest/client";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import getMutationMetaDetailsFromFormData from "@/entities/nodes/object-item-meta-edit/getMutationMetaDetailsFromFormData";
import type { ModelSchema } from "@/entities/schema/types";

interface ObjectItemMetaEditProps {
  row: any;
  schema: ModelSchema;
  type: "attribute" | "relationship";
  attributeOrRelationshipToEdit: any;
  attributeOrRelationshipName: string;
  onSuccess?: () => void;
  onCancel?: () => void;
}

export default function ObjectItemMetaEdit({
  row,
  type,
  attributeOrRelationshipName,
  schema,
  attributeOrRelationshipToEdit,
  onSuccess,
  onCancel,
}: ObjectItemMetaEditProps) {
  const { mutateAsync: updateObject } = useUpdateObjectMutation();

  async function onSubmit(data: any) {
    const updatedObject = getMutationMetaDetailsFromFormData(
      schema,
      data,
      row,
      type,
      attributeOrRelationshipName,
      attributeOrRelationshipToEdit
    );

    if (!Object.keys(updatedObject).length) return;

    try {
      await updateObject({
        objectKind: schema.kind!,
        data: updatedObject,
      });
      await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Metadata updated" />);
      onSuccess?.();
    } catch (e) {
      console.error("Something went wrong while updating the metadata", e);
    }
  }

  return (
    <div className="flex flex-1 bg-white">
      <DynamicForm
        fields={[
          {
            name: "owner",
            label: "Owner",
            type: "relationship",
            relationship: { cardinality: "one", inherited: true, peer: "LineageOwner" } as any,
            defaultValue: getRelationshipDefaultValue({
              objectData: { owner: { node: attributeOrRelationshipToEdit.owner } },
              relationshipName: "owner",
            }),
            parent: attributeOrRelationshipToEdit.owner?.__typename,
          },
          {
            name: "source",
            label: "Source",
            type: "relationship",
            relationship: { cardinality: "one", inherited: true, peer: "LineageSource" } as any,
            defaultValue: getRelationshipDefaultValue({
              objectData: { source: { node: attributeOrRelationshipToEdit.source } },
              relationshipName: "source",
            }),
            parent: attributeOrRelationshipToEdit.source?.__typename,
          },
          {
            attribute: undefined,
            name: "is_protected",
            label: "is protected",
            type: "Checkbox",
            defaultValue: {
              source: { type: "user" },
              value: attributeOrRelationshipToEdit.is_protected,
            },
            rules: {
              required: true,
            },
          },
        ]}
        onCancel={onCancel}
        onSubmit={async (data) => {
          await onSubmit(mapValues(data, (fieldData) => fieldData?.value));
        }}
        className="w-full p-4"
      />
    </div>
  );
}

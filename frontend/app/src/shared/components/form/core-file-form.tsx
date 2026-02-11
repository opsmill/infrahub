import { useState } from "react";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { DynamicField } from "@/shared/components/form/dynamic-form";
import { FileField } from "@/shared/components/form/fields/file.field";
import type { ProfileData } from "@/shared/components/form/object-form";
import type { FormFieldValue } from "@/shared/components/form/type";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { getUpdateMutationFromFormData } from "@/shared/components/form/utils/mutations/getUpdateMutationFromFormData";
import { isRequired } from "@/shared/components/form/utils/validation";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { useUpdateObjectMutation } from "@/entities/nodes/object/domain/update-object.mutation";
import type { NodeCore, NodeObject } from "@/entities/nodes/types";
import { useGetNumberPools } from "@/entities/resource-manager/domain/get-number-pools.query";
import type { NodeSchema, ProfileSchema } from "@/entities/schema/types";

export type CoreFileFormData = Record<string, FormFieldValue>;

export type CoreFileFormProps = {
  className?: string;
  schema: NodeSchema | ProfileSchema;
  profiles?: ProfileData[];
  currentObject?: Record<string, AttributeType | RelationshipType>;
  objectTemplate?: NodeObject | null;
  isFilterForm?: boolean;
  isUpdate?: boolean;
  onSuccess?: (newObject: NodeCore) => void;
  onCancel?: () => void;
};

function getExistingFileInfo(currentObject?: Record<string, AttributeType | RelationshipType>) {
  if (!currentObject) return null;

  const fileName =
    (currentObject.file_name as { value?: string })?.value ||
    (currentObject.name as { value?: string })?.value;

  if (!fileName) return null;

  return {
    fileName,
    fileSize: (currentObject.file_size as { value?: number })?.value,
    contentType: (currentObject.file_type as { value?: string })?.value,
  };
}

export function CoreFileForm({
  className,
  currentObject,
  objectTemplate,
  schema,
  profiles,
  onSuccess,
  onCancel,
  isFilterForm,
  isUpdate = false,
}: CoreFileFormProps) {
  const auth = useAuth();
  const { parentData, parentSchema } = useCurrentFormContext();
  const createObject = useCreateObjectMutation();
  const updateObject = useUpdateObjectMutation();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const existingFile = getExistingFileInfo(currentObject);

  const { data: numberPools, isPending } = useGetNumberPools({
    objectKinds: [schema.kind as string, ...(schema.inherit_from ?? [])],
  });

  if (isPending) return <LoadingIndicator className="my-4" />;

  const fields = getFormFieldsFromSchema({
    schema,
    profiles,
    initialObject: currentObject,
    objectTemplate,
    auth,
    isFilterForm,
    pools: numberPools,
    isUpdate,
    parentSchema,
    parentData,
  });

  const formDefaultValues: Record<string, unknown> = Object.fromEntries(
    fields.map((field) => [field.name, field.defaultValue])
  );

  async function onSubmit(formData: CoreFileFormData) {
    if (!isUpdate && !selectedFile) return;

    const mutationParams = {
      objectKind: schema.kind as string,
      profileIds: profiles?.map((profile) => profile.id),
      ...(selectedFile && { file: selectedFile }),
    };

    try {
      if (isUpdate) {
        const updatedData: Record<string, unknown> = getUpdateMutationFromFormData({
          fields,
          formData,
        });
        if (currentObject?.id) updatedData.id = currentObject.id;

        await updateObject.mutateAsync(
          { ...mutationParams, data: updatedData },
          {
            onSuccess: async (updatedNode) => {
              // Invalidate file queries to refresh the UI
              await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });

              toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schema?.name} updated`} />, {
                toastId: `alert-success-${schema?.name}-updated`,
              });
              if (onSuccess) await onSuccess(updatedNode);
            },
          }
        );
      } else {
        const newObject = getCreateMutationFromFormData(fields, formData, objectTemplate?.id);

        await createObject.mutateAsync(
          { ...mutationParams, data: newObject },
          {
            onSuccess: async (newNode) => {
              toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schema?.name} created`} />, {
                toastId: `alert-success-${schema?.name}-created`,
              });
              if (onSuccess) await onSuccess(newNode);
            },
          }
        );
      }
    } catch (error) {
      console.error("An error occurred during file operation: ", error);
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={`Failed to ${isUpdate ? "update" : "upload"} file`}
        />,
        { toastId: "alert-error-file-operation" }
      );
    }
  }

  return (
    <div className={classNames("flex flex-1 flex-col overflow-auto bg-white p-4", className)}>
      <Form onSubmit={onSubmit} defaultValues={formDefaultValues} className="space-y-4">
        <FileField
          name="file"
          label="File"
          rules={!isUpdate ? { required: true, validate: { required: isRequired } } : undefined}
          selectedFile={selectedFile}
          existingFile={existingFile}
          onFileSelect={setSelectedFile}
        />

        {fields.map((field) => (
          <DynamicField key={`${field.type}_${field.name}`} {...field} />
        ))}

        <div className="text-right">
          {onCancel && (
            <Button variant="outline" className="mr-2" onClick={onCancel}>
              Cancel
            </Button>
          )}
          <FormSubmit>Save</FormSubmit>
        </div>
      </Form>
    </div>
  );
}

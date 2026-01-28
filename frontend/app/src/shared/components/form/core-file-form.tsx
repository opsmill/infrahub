import { useRef } from "react";
import { toast } from "react-toastify";

import { Button } from "@/shared/components/buttons/button-primitive";
import { FileInfoCard } from "@/shared/components/file/file-info-card";
import { DynamicField } from "@/shared/components/form/dynamic-form";
import { LabelFormField } from "@/shared/components/form/fields/common";
import type { ProfileData } from "@/shared/components/form/object-form";
import type { FormFieldValue } from "@/shared/components/form/type";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { FileDropzone } from "@/shared/components/inputs/file-dropzone";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormField, FormMessage, FormSubmit } from "@/shared/components/ui/form";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";
import type { NodeCore, NodeObject } from "@/entities/nodes/types";
import { useGetNumberPools } from "@/entities/resource-manager/domain/get-number-pools.query";
import type { NodeSchema, ProfileSchema } from "@/entities/schema/types";

export type CoreFileFormData = Record<string, FormFieldValue> & {
  file?: File | null;
};

/** Existing file info extracted from currentObject during edit */
export interface ExistingFileInfo {
  fileName: string;
  fileSize?: number;
  contentType?: string;
}

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

/**
 * Extracts existing file information from currentObject attributes.
 * Used during edit mode to show current file details.
 */
function getExistingFileInfo(
  currentObject?: Record<string, AttributeType | RelationshipType>
): ExistingFileInfo | null {
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
  isUpdate,
}: CoreFileFormProps) {
  const auth = useAuth();
  const { parentData, parentSchema } = useCurrentFormContext();
  const createObject = useCreateObjectMutation();
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const formDefaultValues: Record<string, unknown> = {
    file: null,
    ...Object.fromEntries(fields.map((field) => [field.name, field.defaultValue])),
  };

  async function onSubmit(formData: CoreFileFormData) {
    const { file, ...rest } = formData;

    try {
      const newObject = getCreateMutationFromFormData(fields, rest, objectTemplate?.id);

      await createObject.mutateAsync(
        {
          objectKind: schema.kind as string,
          data: newObject,
          profileIds: profiles?.map((profile) => profile.id),
          file: file ?? undefined,
        },
        {
          onSuccess: async (newNode) => {
            toast(
              <Alert
                type={ALERT_TYPES.SUCCESS}
                message={`${schema?.name} ${isUpdate ? "updated" : "created"}`}
              />,
              {
                toastId: `alert-success-${schema?.name}-${isUpdate ? "updated" : "created"}`,
              }
            );

            if (onSuccess) await onSuccess(newNode);
          },
          onError: (error) => {
            console.error("An error occurred while saving the file: ", error);
          },
        }
      );
    } catch (error) {
      console.error("An error occurred during file upload: ", error);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Failed to upload file" />, {
        toastId: "alert-error-upload",
      });
    }
  }

  // File is required only for create, not for update (existing file is kept if not replaced)
  const fileValidationRules = isUpdate ? {} : { required: "File is required" };

  return (
    <div className={classNames("flex flex-1 flex-col overflow-auto bg-white p-4", className)}>
      <Form onSubmit={onSubmit} defaultValues={formDefaultValues} className="space-y-4">
        <FormField
          name="file"
          rules={fileValidationRules}
          render={({ field, fieldState }) => {
            const selectedFile = field.value as File | null;

            const handleFileSelect = (file: File) => {
              field.onChange(file);
            };

            const handleReplaceFile = () => {
              fileInputRef.current?.click();
            };

            const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
              const file = event.target.files?.[0];
              if (file) {
                field.onChange(file);
              }
              event.target.value = "";
            };

            // Show selected file (new upload) or existing file (during edit)
            const showFileInfo = selectedFile || (isUpdate && existingFile);
            const displayFileName = selectedFile?.name || existingFile?.fileName || "";
            const displayFileSize = selectedFile?.size ?? existingFile?.fileSize;
            const displayContentType =
              (selectedFile?.type || undefined) ?? existingFile?.contentType;

            return (
              <div className="space-y-2">
                <LabelFormField label="File" required={!isUpdate} />
                {showFileInfo ? (
                  <>
                    <FileInfoCard
                      fileName={displayFileName}
                      fileSize={displayFileSize}
                      contentType={displayContentType}
                      onReplace={handleReplaceFile}
                    />
                    <input
                      ref={fileInputRef}
                      type="file"
                      className="hidden"
                      onChange={handleFileInputChange}
                    />
                  </>
                ) : (
                  <FileDropzone onFileSelect={handleFileSelect} hasError={!!fieldState.error} />
                )}
                <FormMessage />
              </div>
            );
          }}
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

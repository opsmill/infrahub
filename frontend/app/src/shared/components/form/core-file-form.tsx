import { useRef, useState } from "react";
import { toast } from "react-toastify";

import { FileInfoCard } from "@/shared/components/file/file-info-card";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { LabelFormField } from "@/shared/components/form/fields/common";
import type { ProfileData } from "@/shared/components/form/object-form";
import type { FormFieldValue } from "@/shared/components/form/type";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { FileDropzone } from "@/shared/components/inputs/file-dropzone";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";
import type { NodeCore, NodeObject } from "@/entities/nodes/types";
import { useGetNumberPools } from "@/entities/resource-manager/domain/get-number-pools.query";
import type { NodeSchema, ProfileSchema } from "@/entities/schema/types";

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

export function CoreFileForm({
  className,
  currentObject,
  objectTemplate,
  schema,
  profiles,
  onSuccess,
  isFilterForm,
  isUpdate,
  ...props
}: CoreFileFormProps) {
  const auth = useAuth();
  const { parentData, parentSchema } = useCurrentFormContext();
  const createObject = useCreateObjectMutation();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  async function onSubmitCreate(formData: Record<string, FormFieldValue>) {
    setIsUploading(true);

    try {
      const newObject = getCreateMutationFromFormData(fields, formData, objectTemplate?.id);

      await createObject.mutateAsync(
        {
          objectKind: schema.kind as string,
          data: newObject,
          profileIds: profiles?.map((profile) => profile.id),
          file: selectedFile ?? undefined,
        },
        {
          onSuccess: async (newNode) => {
            toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schema?.name} created`} />, {
              toastId: `alert-success-${schema?.name}-created`,
            });

            if (onSuccess) await onSuccess(newNode);
          },
          onError: (error) => {
            console.error("An error occurred while creating the file: ", error);
          },
        }
      );
    } catch (error) {
      console.error("An error occurred during file upload: ", error);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Failed to upload file" />, {
        toastId: "alert-error-upload",
      });
    } finally {
      setIsUploading(false);
    }
  }

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
  };

  const handleReplaceFile = () => {
    fileInputRef.current?.click();
  };

  const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
    event.target.value = "";
  };

  return (
    <div className={classNames("flex flex-1 flex-col overflow-auto bg-white p-4", className)}>
      <div className="mb-4">
        <LabelFormField label="File" className="mb-1" />
        {selectedFile ? (
          <>
            <FileInfoCard
              fileName={selectedFile.name}
              fileSize={selectedFile.size}
              contentType={selectedFile.type || undefined}
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
          <FileDropzone onFileSelect={handleFileSelect} />
        )}
      </div>

      <DynamicForm
        fields={fields}
        onSubmit={onSubmitCreate}
        submitLabel={isUploading ? "Uploading..." : "Save"}
        {...props}
      />
    </div>
  );
}

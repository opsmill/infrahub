import { EyeIcon, RefreshCwIcon, Trash2Icon } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "react-toastify";

import { apiClient } from "@/shared/api/rest/client";
import DynamicForm from "@/shared/components/form/dynamic-form";
import type { ProfileData } from "@/shared/components/form/object-form";
import type { FormFieldValue } from "@/shared/components/form/type";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { FileDropzone } from "@/shared/components/inputs/file-dropzone";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { classNames, formatFileSize } from "@/shared/utils/common";
import { getFileIcon } from "@/shared/utils/file";

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

  async function uploadFile(file: File): Promise<string> {
    const formData = new FormData();
    formData.append("file", file);

    const response = await apiClient.POST("/api/storage/upload/file", {
      // @ts-expect-error - FormData type mismatch with generated types
      body: formData,
    });

    if (response.error) {
      throw new Error("Failed to upload file");
    }

    return response.data.identifier;
  }

  async function onSubmitCreate(formData: Record<string, FormFieldValue>) {
    setIsUploading(true);

    try {
      let storageId: string | undefined;

      if (selectedFile) {
        storageId = await uploadFile(selectedFile);
      }

      const newObject = getCreateMutationFromFormData(fields, formData, objectTemplate?.id);

      // Add file-specific attributes
      const fileData = {
        ...newObject,
        ...(storageId && { storage_id: { value: storageId } }),
        ...(selectedFile && {
          file_name: { value: selectedFile.name },
          file_size: { value: selectedFile.size },
          content_type: { value: selectedFile.type || "application/octet-stream" },
        }),
      };

      await createObject.mutateAsync(
        {
          objectKind: schema.kind as string,
          data: fileData,
          profileIds: profiles?.map((profile) => profile.id),
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

  const handleViewFile = () => {
    if (!selectedFile) return;
    const url = URL.createObjectURL(selectedFile);
    window.open(url, "_blank");
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

  const handleRemoveFile = () => {
    setSelectedFile(null);
  };

  const FileIconComponent = selectedFile ? getFileIcon(selectedFile.type) : null;

  return (
    <div className={classNames("flex flex-1 flex-col overflow-auto bg-white p-4", className)}>
      <div className="mb-4">
        <label className="mb-2 block font-medium text-gray-700 text-sm">File</label>
        {selectedFile && FileIconComponent ? (
          <div className="rounded-md border bg-gray-50 p-3">
            <div className="flex items-center justify-between">
              <FileIconComponent className="mr-3 size-5 shrink-0 text-gray-500" />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-gray-700 text-sm">{selectedFile.name}</p>
                <div className="mt-1 flex items-center gap-2 text-gray-500 text-xs">
                  <span>{formatFileSize(selectedFile.size)}</span>
                  <span>•</span>
                  <span>{selectedFile.type || "Unknown type"}</span>
                  <span>•</span>
                  <span>Added {new Date().toLocaleDateString()}</span>
                </div>
              </div>
              <div className="ml-4 flex items-center gap-1">
                <button
                  type="button"
                  onClick={handleViewFile}
                  className="rounded p-1.5 text-gray-500 hover:bg-gray-200 hover:text-gray-700"
                  title="View file"
                >
                  <EyeIcon className="size-4" />
                </button>
                <button
                  type="button"
                  onClick={handleReplaceFile}
                  className="rounded p-1.5 text-gray-500 hover:bg-gray-200 hover:text-gray-700"
                  title="Replace file"
                >
                  <RefreshCwIcon className="size-4" />
                </button>
                <button
                  type="button"
                  onClick={handleRemoveFile}
                  className="rounded p-1.5 text-gray-500 hover:bg-red-100 hover:text-red-600"
                  title="Remove file"
                >
                  <Trash2Icon className="size-4" />
                </button>
              </div>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={handleFileInputChange}
            />
          </div>
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

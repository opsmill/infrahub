import type { ComponentProps } from "react";

import { FileInfoCard } from "@/shared/components/file/ui/file-info-card";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import { FileDropzone } from "@/shared/components/inputs/file-dropzone";
import {
  FormField,
  type FormField as FormFieldType,
  FormInput,
  FormMessage,
} from "@/shared/components/ui/form";

import type { AttributeSchema } from "@/entities/schema/types";

export interface FileFieldProps {
  attribute?: AttributeSchema;
  defaultValue?: FormAttributeValue;
  description?: string;
  disabled?: boolean;
  label?: string;
  name: string;
  rules?: ComponentProps<typeof FormFieldType>["rules"];
  isBulkUpdate?: boolean;
  shouldUnregister?: boolean;
  selectedFile: File | null;
  existingFile?: {
    fileName: string;
    fileSize?: number;
    contentType?: string;
  } | null;
  onFileSelect: (file: File) => void;
}

export function FileField({
  attribute,
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  description,
  disabled,
  label = "File",
  name,
  rules,
  isBulkUpdate,
  shouldUnregister,
  selectedFile,
  existingFile,
  onFileSelect,
}: FileFieldProps) {
  return (
    <FormField
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      shouldUnregister={shouldUnregister}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;
        const hasFile = selectedFile !== null;
        const hasExistingFile = !!existingFile?.fileName;
        const showFileCard = hasFile || hasExistingFile;

        return (
          <div className="space-y-2">
            <LabelFormField
              label={label}
              required={!!rules?.required}
              description={description}
              fieldData={fieldData}
            />

            <FormInput>
              {showFileCard ? (
                <FileInfoCard
                  fileName={selectedFile?.name ?? existingFile?.fileName ?? ""}
                  fileSize={selectedFile?.size ?? existingFile?.fileSize}
                  contentType={selectedFile?.type || existingFile?.contentType}
                  onFileSelect={onFileSelect}
                />
              ) : (
                <FileDropzone onFileSelect={onFileSelect} isDisabled={disabled} />
              )}
            </FormInput>

            {!disabled && attribute && canDisplayResetActions(attribute, isBulkUpdate) && (
              <ResetAction field={field} defaultValue={defaultValue} />
            )}

            <FormMessage />
          </div>
        );
      }}
    />
  );
}

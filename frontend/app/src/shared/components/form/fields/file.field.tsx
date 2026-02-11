import { FileInfoCard } from "@/shared/components/file/ui/file-info-card";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import type { FormAttributeValue, FormFieldProps } from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import { FileDropzone } from "@/shared/components/inputs/file-dropzone";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

export interface ExistingFileInfo {
  fileName: string;
  fileSize?: number;
  contentType?: string;
}

export interface FileFieldProps extends Omit<FormFieldProps, "attribute"> {
  attribute?: FormFieldProps["attribute"];
  selectedFile: File | null;
  existingFile?: ExistingFileInfo | null;
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

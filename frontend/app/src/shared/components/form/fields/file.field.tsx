import { useFormContext } from "react-hook-form";

import { FileInfoCard } from "@/shared/components/file/ui/file-info-card";
import { LabelFormField } from "@/shared/components/form/fields/common";
import { FileDropzone } from "@/shared/components/inputs/file-dropzone";
import { classNames } from "@/shared/utils/common";

export interface FileFieldProps {
  label?: string;
  required?: boolean;
  selectedFile: File | null;
  existingFile?: {
    fileName: string;
    fileSize?: number;
    contentType?: string;
  } | null;
  onFileSelect: (file: File) => void;
}

export function FileField({
  label = "File",
  required = false,
  selectedFile,
  existingFile,
  onFileSelect,
}: FileFieldProps) {
  const { formState } = useFormContext();

  const hasFile = selectedFile !== null;
  const hasExistingFile = !!existingFile?.fileName;
  const showFileCard = hasFile || hasExistingFile;
  const showError = formState.submitCount > 0 && required && !hasFile;

  return (
    <div className="space-y-2">
      <LabelFormField label={label} required={required} />

      {showFileCard ? (
        <FileInfoCard
          fileName={selectedFile?.name ?? existingFile?.fileName ?? ""}
          fileSize={selectedFile?.size ?? existingFile?.fileSize}
          contentType={selectedFile?.type || existingFile?.contentType}
          onFileSelect={onFileSelect}
        />
      ) : (
        <FileDropzone
          onFileSelect={onFileSelect}
          className={classNames(showError && "border-red-500")}
        />
      )}

      {showError && <p className="text-red-600 text-sm">{label} is required</p>}
    </div>
  );
}

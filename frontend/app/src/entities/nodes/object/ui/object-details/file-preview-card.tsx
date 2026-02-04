import { ObjectFile } from "@/entities/object-file/ui/object-file";
import { FileInfoCard } from "@/shared/components/file/ui/file-info-card";

interface FilePreviewCardProps {
  nodeId: string;
  fileName: string;
  fileSize?: number;
  contentType?: string;
}

export function FilePreviewCard({ nodeId, fileName, fileSize, contentType }: FilePreviewCardProps) {
  return (
    <div className="flex flex-col gap-2">
      <FileInfoCard fileName={fileName} fileSize={fileSize} contentType={contentType} />

      <ObjectFile nodeId={nodeId} fileName={fileName} contentType={contentType} />
    </div>
  );
}

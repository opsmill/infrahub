import { FileInfoCard } from "@/shared/components/file/file-info-card";
import { FileViewer, FileViewerFallback } from "@/shared/components/file/file-viewer";
import { CONFIG } from "@/shared/config/config";

interface FilePreviewCardProps {
  storageId?: string;
  fileName: string;
  fileSize?: number;
  contentType?: string;
}

export function FilePreviewCard({
  storageId,
  fileName,
  fileSize,
  contentType,
}: FilePreviewCardProps) {
  const fileUrl = storageId ? CONFIG.ARTIFACTS_CONTENT_URL(storageId) : undefined;

  return (
    <div className="flex flex-col gap-2">
      <FileInfoCard fileName={fileName} fileSize={fileSize} contentType={contentType} />

      {fileUrl ? (
        <FileViewer url={fileUrl} fileName={fileName} contentType={contentType} />
      ) : (
        <FileViewerFallback fileName={fileName} contentType={contentType} />
      )}
    </div>
  );
}

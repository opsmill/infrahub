import { FileInfoCard } from "@/shared/components/file/ui/file-info-card";
import { FileViewer } from "@/shared/components/file/ui/file-viewer";
import { FileViewerFallback } from "@/shared/components/file/ui/file-viewer-fallback";
import { CONFIG } from "@/shared/config/config";

interface FilePreviewCardProps {
  nodeId?: string;
  fileName: string;
  fileSize?: number;
  contentType?: string;
}

export function FilePreviewCard({ nodeId, fileName, fileSize, contentType }: FilePreviewCardProps) {
  const previewUrl = nodeId ? CONFIG.FILE_BY_NODE_ID_URL(nodeId, true) : undefined;
  const downloadUrl = nodeId ? CONFIG.FILE_BY_NODE_ID_URL(nodeId, false) : undefined;

  return (
    <div className="flex flex-col gap-2">
      <FileInfoCard fileName={fileName} fileSize={fileSize} contentType={contentType} />

      {previewUrl ? (
        <FileViewer
          url={previewUrl}
          downloadUrl={downloadUrl}
          fileName={fileName}
          contentType={contentType}
        />
      ) : (
        <FileViewerFallback fileName={fileName} contentType={contentType} />
      )}
    </div>
  );
}

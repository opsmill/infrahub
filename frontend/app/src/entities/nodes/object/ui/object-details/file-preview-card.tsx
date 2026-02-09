import { Col } from "@/shared/components/container";
import type { DataViewerContentType } from "@/shared/components/data-viewer/types";
import { FileInfoCard } from "@/shared/components/file/ui/file-info-card";

import { ObjectFile } from "@/entities/object-file/ui/object-file";

interface FilePreviewCardProps {
  nodeId: string;
  fileName: string;
  fileSize?: number;
  contentType?: DataViewerContentType;
}

export function FilePreviewCard({ nodeId, fileName, fileSize, contentType }: FilePreviewCardProps) {
  return (
    <Col>
      <FileInfoCard fileName={fileName} fileSize={fileSize} contentType={contentType} />

      <ObjectFile nodeId={nodeId} fileName={fileName} contentType={contentType} />
    </Col>
  );
}

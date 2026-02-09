import { Col } from "@/shared/components/container";
import { FileInfoCard } from "@/shared/components/file/ui/file-info-card";

import { ObjectFile } from "@/entities/object-file/ui/object-file";

interface FilePreviewCardProps {
  nodeId: string;
  fileName: string;
  fileSize?: number;
  contentType?: string;
}

export function FilePreviewCard({ nodeId, fileName, fileSize, contentType }: FilePreviewCardProps) {
  return (
    <Col>
      <FileInfoCard fileName={fileName} fileSize={fileSize} contentType={contentType} />

      <ObjectFile nodeId={nodeId} fileName={fileName} contentType={contentType} />
    </Col>
  );
}

import { Col } from "@/shared/components/container";
import type { DataViewerContentType } from "@/shared/components/data-viewer/types";
import { FileInfoCard } from "@/shared/components/file/ui/file-info-card";

import type { NodeFileObject } from "@/entities/nodes/types";
import { ObjectFile } from "@/entities/object-file/ui/object-file";

interface FilePreviewCardProps {
  objectData: NodeFileObject;
}

export function FilePreviewCard({ objectData }: FilePreviewCardProps) {
  const fileName = objectData.file_name.value;
  const fileSize = objectData.file_size.value;
  const contentType = objectData.file_type.value as DataViewerContentType;

  return (
    <Col>
      <FileInfoCard fileName={fileName} fileSize={fileSize} contentType={contentType} />

      <ObjectFile nodeId={objectData.id} fileName={fileName} contentType={contentType} />
    </Col>
  );
}

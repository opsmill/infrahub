import { CONTENT_TYPE_CONFIG, DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { DataViewerLinkButton } from "@/shared/components/data-viewer/data-viewer-action-button";
import type { DataViewerContentType } from "@/shared/components/data-viewer/types";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetArtifactFile } from "@/entities/artifacts/domain/get-artifact-file.query";

interface ArtifactFileProps {
  artifactId: string;
  storageId: string;
  url: string;
  contentType: DataViewerContentType;
  className?: string;
}

export function ArtifactFile({
  artifactId,
  storageId,
  url,
  contentType,
  className,
}: ArtifactFileProps) {
  const { data: fileContent, isPending, error } = useGetArtifactFile({ storageId });

  if (isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <NoDataFound message={error.message} />;
  }

  const config = CONTENT_TYPE_CONFIG[contentType] ?? CONTENT_TYPE_CONFIG["text/plain"];

  return (
    <DataViewer
      title={config.label}
      data={fileContent}
      fileName={`${artifactId}.${config.extension}`}
      contentType={contentType}
      actions={
        <DataViewerLinkButton href={url} target="_blank" rel="noopener noreferrer">
          Raw
        </DataViewerLinkButton>
      }
      className={className}
    />
  );
}

import { DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { DataViewerLinkButton } from "@/shared/components/data-viewer/data-viewer-action-button";
import { DataViewerCopyButton } from "@/shared/components/data-viewer/data-viewer-copy-button";
import { DataViewerDownloadButton } from "@/shared/components/data-viewer/data-viewer-download-button";
import type { DataViewerContentType } from "@/shared/components/data-viewer/types";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { getArtifactFileDownloadUrl } from "@/entities/artifacts/domain/get-artifact-file";
import { useGetArtifactFile } from "@/entities/artifacts/domain/get-artifact-file.query";

export interface ArtifactFileProps {
  storageId: string;
  fileName: string;
  contentType?: DataViewerContentType;
  className?: string;
}

export function ArtifactFile({ storageId, fileName, contentType, className }: ArtifactFileProps) {
  const { data, isPending, error } = useGetArtifactFile({ storageId, contentType });

  if (isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <NoDataFound message={error.message} />;
  }

  if (!data) {
    return <NoDataFound message="File content is empty" />;
  }

  const downloadUrl = getArtifactFileDownloadUrl(storageId);

  return (
    <DataViewer
      data={data}
      contentType={contentType}
      className={className}
      actions={
        <>
          <DataViewerLinkButton href={downloadUrl} target="_blank" rel="noopener noreferrer">
            Raw
          </DataViewerLinkButton>
          <DataViewerDownloadButton value={data} fileName={fileName} contentType={contentType} />
          <DataViewerCopyButton value={data} />
        </>
      }
    />
  );
}

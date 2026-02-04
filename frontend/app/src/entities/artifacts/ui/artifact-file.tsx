import { DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { DataViewerLinkButton } from "@/shared/components/data-viewer/data-viewer-action-button";
import { DataViewerCopyButton } from "@/shared/components/data-viewer/data-viewer-copy-button";
import { DataViewerDownloadButton } from "@/shared/components/data-viewer/data-viewer-download-button";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { CONFIG } from "@/shared/config/config";

import { getArtifactFileDownloadUrl } from "@/entities/artifacts/domain/get-artifact-file";
import { useGetArtifactFile } from "@/entities/artifacts/domain/get-artifact-file.query";

export interface ArtifactFileProps {
  storageId: string;
  fileName: string;
  contentType?: string;
  className?: string;
}

export function ArtifactFile({ storageId, fileName, contentType, className }: ArtifactFileProps) {
  const { data: content, isPending, error } = useGetArtifactFile({ storageId, contentType });

  if (isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <NoDataFound message={error.message} />;
  }

  if (!content) {
    return <NoDataFound message="File content is empty" />;
  }

  const rawUrl = CONFIG.ARTIFACTS_CONTENT_URL(storageId);

  return (
    <DataViewer
      data={content}
      contentType={contentType}
      downloadUrl={getArtifactFileDownloadUrl(storageId)}
      className={className}
      actions={
        <>
          <DataViewerLinkButton href={rawUrl} target="_blank" rel="noopener noreferrer">
            Raw
          </DataViewerLinkButton>
          <DataViewerDownloadButton value={content} fileName={fileName} contentType={contentType} />
          <DataViewerCopyButton value={content} />
        </>
      }
    />
  );
}

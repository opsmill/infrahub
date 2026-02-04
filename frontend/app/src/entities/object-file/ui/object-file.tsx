import { DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { DataViewerLinkButton } from "@/shared/components/data-viewer/data-viewer-action-button";
import { DataViewerCopyButton } from "@/shared/components/data-viewer/data-viewer-copy-button";
import { DataViewerDownloadButton } from "@/shared/components/data-viewer/data-viewer-download-button";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import {
  getObjectFileDownloadUrl,
  getObjectFileRawUrl,
} from "@/entities/object-file/domain/get-object-file";
import { useGetObjectFile } from "@/entities/object-file/domain/get-object-file.query";

export interface ObjectFileProps {
  nodeId: string;
  fileName: string;
  contentType?: string;
  className?: string;
}

export function ObjectFile({ nodeId, fileName, contentType, className }: ObjectFileProps) {
  const { data: content, isPending, error } = useGetObjectFile({ nodeId, contentType });

  if (isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <NoDataFound message={error.message} />;
  }

  if (!content) {
    return <NoDataFound message="File content is empty" />;
  }

  const rawUrl = getObjectFileRawUrl(nodeId);
  const downloadUrl = getObjectFileDownloadUrl(nodeId);

  return (
    <DataViewer
      data={content}
      contentType={contentType}
      className={className}
      actions={
        <>
          <DataViewerLinkButton href={rawUrl} target="_blank" rel="noopener noreferrer">
            Raw
          </DataViewerLinkButton>
          <DataViewerDownloadButton
            value={content}
            fileName={fileName}
            contentType={contentType}
            downloadUrl={downloadUrl}
          />
          <DataViewerCopyButton value={content} />
        </>
      }
    />
  );
}

import { DataViewer } from "@/shared/components/data-viewer/data-viewer";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetArtifactFile } from "@/entities/artifacts/domain/get-artifact-file.query";

export interface ArtifactFileProps {
  storageId: string;
  fileName: string;
  contentType?: string;
  className?: string;
}

export function ArtifactFile({ storageId, fileName, contentType, className }: ArtifactFileProps) {
  const { data: content, isPending, error } = useGetArtifactFile({ storageId });

  if (isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <NoDataFound message={error.message} />;
  }

  if (!content) {
    return <NoDataFound message="File content is empty" />;
  }

  return (
    <DataViewer
      data={content}
      fileName={fileName}
      contentType={contentType}
      className={className}
    />
  );
}

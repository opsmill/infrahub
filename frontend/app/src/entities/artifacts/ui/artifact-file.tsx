import { useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";

import { fetchStream } from "@/shared/api/rest/fetch";
import { CONTENT_TYPE_CONFIG, DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { DataViewerLinkButton } from "@/shared/components/data-viewer/data-viewer-action-button";
import type { DataViewerContentType } from "@/shared/components/data-viewer/types";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

interface ArtifactFileProps {
  artifactId: string;
  url: string;
  contentType: DataViewerContentType;
}

export const ArtifactFile = ({ artifactId, url, contentType }: ArtifactFileProps) => {
  const [isLoading, setIsLoading] = useState(false);
  const [fileContent, setFileContent] = useState<string>();

  const fetchFileDetails = useCallback(async () => {
    if (!url) return;

    setIsLoading(true);

    try {
      const fileResult = await fetchStream(url);
      setFileContent(fileResult);
    } catch (err) {
      console.error("Error loading file content:", err);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading file content" />);
    } finally {
      setIsLoading(false);
    }
  }, [url]);

  useEffect(() => {
    fetchFileDetails();
  }, []);

  if (isLoading) {
    return <LoadingIndicator className="p-4" />;
  }

  if (!fileContent) {
    return <NoDataFound message="No file found." />;
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
    />
  );
};

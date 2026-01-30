import { DownloadIcon, ExternalLinkIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";

import { fetchStream } from "@/shared/api/rest/fetch";
import { Tooltip } from "@/shared/components/aria/tooltip";
import { Col, Row } from "@/shared/components/container";
import { CONTENT_TYPE_CONFIG, DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { DataViewerLinkButton } from "@/shared/components/data-viewer/data-viewer-action-button";
import type { DataViewerContentType } from "@/shared/components/data-viewer/types";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { getFileIcon } from "@/shared/utils/file";

export interface FileViewerProps {
  url: string;
  fileName: string;
  contentType?: string;
}

export function FileViewer({ url, fileName, contentType }: FileViewerProps) {
  const dataViewerContentType = mapToDataViewerContentType(contentType);

  // For text-based content, we need to fetch and display with DataViewer
  if (dataViewerContentType) {
    return <TextFileViewer url={url} fileName={fileName} contentType={dataViewerContentType} />;
  }

  // For images (except SVG which is handled above)
  if (contentType?.startsWith("image/")) {
    return <ImageViewer url={url} fileName={fileName} />;
  }

  // For PDFs
  if (contentType === "application/pdf") {
    return <PdfViewer url={url} fileName={fileName} />;
  }

  // Fallback for unsupported types
  return <FileViewerFallback url={url} fileName={fileName} contentType={contentType} />;
}

interface TextFileViewerProps {
  url: string;
  fileName: string;
  contentType: DataViewerContentType;
}

function TextFileViewer({ url, fileName, contentType }: TextFileViewerProps) {
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
  }, [fetchFileDetails]);

  if (isLoading) {
    return <LoadingIndicator className="p-4" />;
  }

  if (!fileContent || fileContent === "No file content") {
    return <NoDataFound message="No file found." />;
  }

  const config = CONTENT_TYPE_CONFIG[contentType] ?? CONTENT_TYPE_CONFIG["text/plain"];

  return (
    <DataViewer
      title={config.label}
      data={fileContent}
      fileName={fileName}
      contentType={contentType}
      actions={
        <DataViewerLinkButton href={url} target="_blank" rel="noopener noreferrer">
          Raw
        </DataViewerLinkButton>
      }
    />
  );
}

interface ImageViewerProps {
  url: string;
  fileName: string;
}

function ImageViewer({ url, fileName }: ImageViewerProps) {
  return (
    <Col className="grow rounded-lg bg-neutral-800 p-2 text-neutral-200">
      <Row>
        <span className="grow px-1 font-medium">Image</span>
        <Tooltip message="Download">
          <a
            href={url}
            download={fileName}
            className="rounded-lg border border-transparent p-1 text-sm hover:bg-neutral-600"
          >
            <DownloadIcon className="size-4" />
          </a>
        </Tooltip>
        <Tooltip message="Open in new tab">
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-transparent p-1 text-sm hover:bg-neutral-600"
          >
            <ExternalLinkIcon className="size-4" />
          </a>
        </Tooltip>
      </Row>

      <div className="flex justify-center rounded-lg border border-neutral-700 bg-white p-4">
        <img src={url} alt={fileName} className="max-h-150 max-w-full rounded" />
      </div>
    </Col>
  );
}

interface PdfViewerProps {
  url: string;
  fileName: string;
}

function PdfViewer({ url, fileName }: PdfViewerProps) {
  return (
    <Col className="grow rounded-lg bg-neutral-800 p-2 text-neutral-200">
      <Row>
        <span className="grow px-1 font-medium">PDF</span>
        <Tooltip message="Download">
          <a
            href={url}
            download={fileName}
            className="rounded-lg border border-transparent p-1 text-sm hover:bg-neutral-600"
          >
            <DownloadIcon className="size-4" />
          </a>
        </Tooltip>
        <Tooltip message="Open in new tab">
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-transparent p-1 text-sm hover:bg-neutral-600"
          >
            <ExternalLinkIcon className="size-4" />
          </a>
        </Tooltip>
      </Row>

      <iframe
        src={url}
        title={fileName}
        className="h-150 w-full rounded-lg border border-neutral-700"
      />
    </Col>
  );
}

interface FileViewerFallbackProps {
  url?: string;
  fileName: string;
  contentType?: string;
}

export function FileViewerFallback({ url, fileName, contentType }: FileViewerFallbackProps) {
  const FileIconComponent = getFileIcon(contentType);

  return (
    <Col className="grow rounded-lg bg-neutral-800 p-2 text-neutral-200">
      <Row>
        <span className="grow px-1 font-medium">Preview</span>
        {url && (
          <>
            <Tooltip message="Download">
              <a
                href={url}
                download={fileName}
                className="rounded-lg border border-transparent p-1 text-sm hover:bg-neutral-600"
              >
                <DownloadIcon className="size-4" />
              </a>
            </Tooltip>
            <Tooltip message="Open in new tab">
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg border border-transparent p-1 text-sm hover:bg-neutral-600"
              >
                <ExternalLinkIcon className="size-4" />
              </a>
            </Tooltip>
          </>
        )}
      </Row>

      <div className="flex flex-col items-center justify-center rounded-lg border border-neutral-700 py-12 text-center">
        <FileIconComponent className="mb-3 size-12 text-neutral-500" />
        <p className="text-neutral-400 text-sm">Preview not available for this file type</p>
      </div>
    </Col>
  );
}

function mapToDataViewerContentType(contentType?: string): DataViewerContentType | null {
  if (!contentType) return null;

  const supportedTypes: DataViewerContentType[] = [
    "application/json",
    "application/yaml",
    "application/hcl",
    "application/graphql",
    "image/svg+xml",
    "text/plain",
    "text/markdown",
    "application/xml",
    "text/csv",
  ];

  // Check for exact match
  if (supportedTypes.includes(contentType as DataViewerContentType)) {
    return contentType as DataViewerContentType;
  }

  // Map common variations
  if (contentType === "application/x-yaml") return "application/yaml";
  if (contentType.startsWith("text/")) return "text/plain";

  return null;
}

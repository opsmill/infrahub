import type { ReactNode } from "react";

import { Col, Row } from "@/shared/components/container";
import { Svg } from "@/shared/components/display/svg";
import { CodeViewer } from "@/shared/components/editor/code/code-viewer";
import { CsvTable } from "@/shared/components/editor/csv-table";
import { MarkdownViewer } from "@/shared/components/editor/markdown/markdown-viewer";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { classNames } from "@/shared/utils/common";
import { getFileIcon } from "@/shared/utils/file";

import { DataViewerCopyButton } from "./data-viewer-copy-button";
import { DataViewerDownloadButton } from "./data-viewer-download-button";
import { DataViewerDownloadLinkButton } from "./data-viewer-download-link-button";
import { DataViewerRawButton } from "./data-viewer-raw-button";
import { type DataViewerContentType, getViewerType } from "./types";
import { useGetFileContent } from "./use-get-file-content";

export interface DataViewerProps {
  /** Header title displayed at the top of the viewer */
  title?: string;
  /** File name used for download operations */
  fileName: string;
  /** MIME content type - determines rendering mode */
  contentType?: string;
  /** Custom action buttons to display in header */
  actions?: ReactNode;
  /** Additional CSS classes */
  className?: string;
  /** Pre-fetched content string (mutually exclusive with url) */
  data?: string;
  /** URL to fetch content from (mutually exclusive with data) */
  url?: string;
  /** Separate download URL if different from content URL */
  downloadUrl?: string;
}

export function DataViewer({
  title,
  data,
  url,
  downloadUrl,
  fileName,
  contentType,
  actions,
  className,
}: DataViewerProps) {
  const viewerType = getViewerType(contentType);

  // URL-based fetching for text content
  const shouldFetch = url && !data && viewerType.type === "text";
  const { data: fetchedContent, isPending, error } = useGetFileContent(shouldFetch ? url : null);

  const resolvedContent = data ?? fetchedContent;
  const resolvedTitle =
    title ??
    (viewerType.type === "text"
      ? CONTENT_TYPE_CONFIG[viewerType.dataViewerContentType]?.label
      : "Preview");

  if (shouldFetch && isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (shouldFetch && error) {
    return <NoDataFound message={error.message} />;
  }

  return (
    <Col className={classNames("grow rounded-lg bg-neutral-800 p-2 text-neutral-200", className)}>
      <Row>
        <span className="grow px-1 font-medium">{resolvedTitle}</span>
        {actions}
        {url && <DataViewerRawButton href={url} />}
        {viewerType.type === "text" && resolvedContent && (
          <>
            <DataViewerDownloadButton
              value={resolvedContent}
              fileName={fileName}
              contentType={viewerType.dataViewerContentType}
            />
            <DataViewerCopyButton value={resolvedContent} />
          </>
        )}
        {(() => {
          const downloadHref = downloadUrl ?? url;
          return viewerType.type !== "text" && downloadHref ? (
            <DataViewerDownloadLinkButton href={downloadHref} fileName={fileName} />
          ) : null;
        })()}
      </Row>

      <DataViewerContent
        viewerType={viewerType}
        content={resolvedContent}
        url={url}
        fileName={fileName}
        contentType={contentType}
      />
    </Col>
  );
}

export const CONTENT_TYPE_CONFIG: Record<
  DataViewerContentType,
  {
    extension: string;
    label: string;
    language?: string;
  }
> = {
  "application/json": { extension: "json", language: "json", label: "JSON" },
  "text/markdown": { extension: "md", language: "markdown", label: "Markdown" },
  "application/yaml": { extension: "yaml", language: "yaml", label: "YAML" },
  "application/hcl": { extension: "hcl", language: "hcl", label: "HCL" },
  "application/graphql": { extension: "graphql", language: "graphql", label: "GraphQL" },
  "image/svg+xml": { extension: "svg", language: "svg", label: "SVG" },
  "text/plain": { extension: "txt", language: "text", label: "text" },
  "application/xml": { extension: "xml", language: "xml", label: "XML" },
  "text/csv": { extension: "csv", language: "csv", label: "CSV" },
} as const;

interface DataViewerContentProps {
  viewerType: ReturnType<typeof getViewerType>;
  content: string | null | undefined;
  url?: string;
  fileName: string;
  contentType?: string;
}

function DataViewerContent({
  viewerType,
  content,
  url,
  fileName,
  contentType,
}: DataViewerContentProps) {
  switch (viewerType.type) {
    case "text": {
      if (!content) {
        return <NoDataFound message="File content is empty" />;
      }
      return <TextContent contentType={viewerType.dataViewerContentType} content={content} />;
    }

    case "image": {
      if (!url) return <NoDataFound message="Image URL is required" />;
      return (
        <div className="flex justify-center rounded-lg border border-neutral-700 bg-white p-4">
          <img src={url} alt={fileName} className="max-h-150 max-w-full rounded" />
        </div>
      );
    }

    case "pdf": {
      if (!url) return <NoDataFound message="PDF URL is required" />;
      return (
        <iframe
          src={url}
          title={fileName}
          className="h-150 w-full rounded-lg border border-neutral-700"
        />
      );
    }

    case "unsupported": {
      const FileIconComponent = getFileIcon(contentType);
      return (
        <div className="flex flex-col items-center justify-center rounded-lg border border-neutral-700 py-12 text-center">
          <FileIconComponent className="mb-3 size-12 text-neutral-500" />
          <p className="text-neutral-400 text-sm">Preview not available for this file type</p>
        </div>
      );
    }
  }
}

function TextContent({
  contentType,
  content,
}: {
  contentType: DataViewerContentType;
  content: string;
}) {
  const config = CONTENT_TYPE_CONFIG[contentType] ?? CONTENT_TYPE_CONFIG["text/plain"];

  switch (contentType) {
    case "text/markdown": {
      return <MarkdownViewer>{content}</MarkdownViewer>;
    }
    case "image/svg+xml": {
      return (
        <Svg value={content} className="grow rounded-lg border border-neutral-700 shadow-sm" />
      );
    }
    case "text/csv": {
      return (
        <ScrollArea scrollX scrollBarClassName="bg-transparent">
          <CsvTable content={content} />
        </ScrollArea>
      );
    }
    default: {
      return (
        <ScrollArea
          scrollX
          className="grow rounded-lg border border-neutral-700 shadow-sm"
          scrollBarClassName="bg-transparent"
        >
          <CodeViewer language={config.language} customStyle={{ margin: 0 }}>
            {content}
          </CodeViewer>
        </ScrollArea>
      );
    }
  }
}

import type { ReactNode } from "react";

import { Col, Row } from "@/shared/components/container";
import { Svg } from "@/shared/components/display/svg";
import { CodeViewer } from "@/shared/components/editor/code/code-viewer";
import { CsvTable } from "@/shared/components/editor/csv-table";
import { MarkdownViewer } from "@/shared/components/editor/markdown/markdown-viewer";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { classNames } from "@/shared/utils/common";
import { getFileIcon } from "@/shared/utils/file";

import { DataViewerCopyButton } from "./data-viewer-copy-button";
import { DataViewerDownloadButton } from "./data-viewer-download-button";
import { getViewerType, type TextContentType, type ViewerType } from "./types";

export interface DataViewerProps {
  data: string;
  fileName: string;
  contentType?: string;
  actions?: ReactNode;
  className?: string;
}

export function DataViewer({ data, fileName, contentType, actions, className }: DataViewerProps) {
  const viewerType = getViewerType(contentType);
  const config =
    viewerType.type === "text" ? TEXT_CONTENT_TYPE_CONFIG[viewerType.textContentType] : null;
  const title = config?.label ?? "Preview";

  return (
    <Col className={classNames("grow rounded-lg bg-neutral-800 p-2 text-neutral-200", className)}>
      <Row>
        <span className="grow px-1 font-medium">{title}</span>
        {actions}
        <DataViewerDownloadButton value={data} fileName={fileName} contentType={contentType} />
        <DataViewerCopyButton value={data} />
      </Row>

      <DataViewerContent viewerType={viewerType} content={data} contentType={contentType} />
    </Col>
  );
}

export const TEXT_CONTENT_TYPE_CONFIG: Record<
  TextContentType,
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
  "text/plain": { extension: "txt", language: "text", label: "Text" },
  "application/xml": { extension: "xml", language: "xml", label: "XML" },
  "text/csv": { extension: "csv", language: "csv", label: "CSV" },
} as const;

interface DataViewerContentProps {
  viewerType: ViewerType;
  content: string;
  contentType?: string;
}

function DataViewerContent({ viewerType, content, contentType }: DataViewerContentProps) {
  switch (viewerType.type) {
    case "text": {
      return <TextContent textContentType={viewerType.textContentType} content={content} />;
    }

    case "image": {
      const dataUrl = `data:${viewerType.imageContentType};base64,${content}`;
      return (
        <div className="flex justify-center rounded-lg border border-neutral-700 bg-white p-4">
          <img src={dataUrl} alt="Preview" className="max-h-150 max-w-full rounded" />
        </div>
      );
    }

    case "pdf": {
      const dataUrl = `data:application/pdf;base64,${content}`;
      return (
        <iframe
          src={dataUrl}
          title="PDF Preview"
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
  textContentType,
  content,
}: {
  textContentType: TextContentType;
  content: string;
}) {
  const config =
    TEXT_CONTENT_TYPE_CONFIG[textContentType] ?? TEXT_CONTENT_TYPE_CONFIG["text/plain"];

  switch (textContentType) {
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

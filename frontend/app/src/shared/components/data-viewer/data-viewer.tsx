import type { ReactNode } from "react";

import { Col, Row } from "@/shared/components/container";
import { Svg } from "@/shared/components/display/svg";
import { CodeViewer } from "@/shared/components/editor/code/code-viewer";
import { CsvTable } from "@/shared/components/editor/csv-table";
import { MarkdownViewer } from "@/shared/components/editor/markdown/markdown-viewer";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { classNames } from "@/shared/utils/common";

import type { ArtifactContentType } from "@/entities/artifacts/types";

import { DataViewerCopyButton } from "./data-viewer-copy-button";
import { DataViewerDownloadButton } from "./data-viewer-download-button";

export interface DataViewerProps {
  title: string;
  data: string;
  fileName: string;
  contentType?: ArtifactContentType;
  actions?: ReactNode;
  className?: string;
}

export function DataViewer({
  title,
  data,
  fileName,
  contentType,
  actions,
  className,
  ...props
}: DataViewerProps) {
  return (
    <Col
      className={classNames("grow rounded-lg bg-neutral-800 p-2 text-neutral-200", className)}
      {...props}
    >
      <Row>
        <span className="grow px-1 font-medium">{title}</span>
        {actions}
        <DataViewerDownloadButton value={data} fileName={fileName} contentType={contentType} />
        <DataViewerCopyButton value={data} />
      </Row>

      <FileContent contentType={contentType} fileContent={data} />
    </Col>
  );
}

export const CONTENT_TYPE_CONFIG: Record<
  ArtifactContentType,
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

function FileContent({
  contentType = "text/plain",
  fileContent,
}: {
  contentType?: ArtifactContentType;
  fileContent: string;
}) {
  const config = CONTENT_TYPE_CONFIG[contentType] ?? CONTENT_TYPE_CONFIG["text/plain"];

  switch (contentType) {
    case "text/markdown": {
      return <MarkdownViewer>{fileContent}</MarkdownViewer>;
    }
    case "image/svg+xml": {
      return (
        <Svg value={fileContent} className="grow rounded-lg border border-neutral-700 shadow-sm" />
      );
    }
    case "text/csv": {
      return (
        <ScrollArea scrollX scrollBarClassName="bg-transparent">
          <CsvTable content={fileContent} />
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
            {fileContent}
          </CodeViewer>
        </ScrollArea>
      );
    }
  }
}

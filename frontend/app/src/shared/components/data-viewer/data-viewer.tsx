import { EyeOffIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Col, Row } from "@/shared/components/container";
import type { DataViewerContentType } from "@/shared/components/data-viewer/types";
import { Svg } from "@/shared/components/display/svg";
import { CodeViewer } from "@/shared/components/editor/code/code-viewer";
import { CsvTable } from "@/shared/components/editor/csv-table";
import { MarkdownViewer } from "@/shared/components/editor/markdown/markdown-viewer";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { classNames } from "@/shared/utils/common";

export interface DataViewerProps {
  title?: string;
  data: string;
  contentType?: DataViewerContentType;
  actions?: ReactNode;
  className?: string;
}

export function DataViewer({
  data,
  title = "Preview",
  contentType = "text/plain",
  actions,
  className,
}: DataViewerProps) {
  return (
    <Col className={classNames("grow rounded-lg bg-neutral-800 p-2 text-neutral-200", className)}>
      <Row>
        <span className="grow px-1 font-medium">{title}</span>
        {actions}
      </Row>

      <DataViewerContent contentType={contentType} content={data} />
    </Col>
  );
}

function DataViewerContent({
  contentType,
  content,
}: {
  contentType: DataViewerContentType;
  content: string;
}) {
  switch (contentType) {
    case "text/markdown":
      return <MarkdownViewer>{content}</MarkdownViewer>;

    case "image/svg+xml":
      return (
        <Svg value={content} className="grow rounded-lg border border-neutral-700 shadow-sm" />
      );

    case "text/csv":
      return (
        <ScrollArea scrollX scrollBarClassName="bg-transparent">
          <CsvTable content={content} />
        </ScrollArea>
      );

    case "application/pdf":
      return (
        <iframe
          src={`data:application/pdf;base64,${content}`}
          title="PDF Preview"
          className="h-150 w-full rounded-lg border border-neutral-700"
        />
      );

    case "image/png":
    case "image/jpeg":
    case "image/gif":
    case "image/webp":
    case "image/bmp":
    case "image/x-icon":
      return (
        <div className="flex justify-center rounded-lg border border-neutral-700 bg-white p-4">
          <img
            src={`data:${contentType};base64,${content}`}
            alt="Preview"
            className="max-h-150 max-w-full rounded"
          />
        </div>
      );

    case "application/json":
    case "application/yaml":
    case "application/x-yaml":
    case "application/hcl":
    case "application/graphql":
    case "application/xml":
    case "application/javascript":
    case "application/typescript":
    case "application/x-sh":
    case "application/x-python":
    case "application/toml":
    case "application/x-toml":
    case "text/plain":
      return <TextViewer content={content} language={getTextLanguage(contentType)} />;

    default:
      if (contentType.startsWith("text/")) {
        return <TextViewer content={content} language="text" />;
      }

      return (
        <div className="flex grow flex-col items-center justify-center gap-2 rounded-lg border border-neutral-700 p-8 text-neutral-400">
          <EyeOffIcon className="size-8" />
          <p>This file can&#39;t be previewed</p>
          <p className="text-sm">{contentType}</p>
        </div>
      );
  }
}

function TextViewer({ content, language }: { content: string; language: string }) {
  return (
    <ScrollArea
      scrollX
      className="grow rounded-lg border border-neutral-700 shadow-sm"
      scrollBarClassName="bg-transparent"
    >
      <CodeViewer language={language} customStyle={{ margin: 0 }}>
        {content}
      </CodeViewer>
    </ScrollArea>
  );
}

function getTextLanguage(contentType: string): string {
  switch (contentType) {
    case "application/json":
      return "json";
    case "application/yaml":
    case "application/x-yaml":
      return "yaml";
    case "application/hcl":
      return "hcl";
    case "application/graphql":
      return "graphql";
    case "application/xml":
      return "xml";
    case "application/javascript":
      return "javascript";
    case "application/typescript":
      return "typescript";
    case "application/x-sh":
      return "bash";
    case "application/x-python":
      return "python";
    case "application/toml":
    case "application/x-toml":
      return "toml";
    default:
      return "text";
  }
}

import type { ReactNode } from "react";

import { Col, Row } from "@/shared/components/container";
import {
  type DataViewerContentType,
  isImageContentType,
  isPdfContentType,
  isTextContentType,
  type TextContentType,
} from "@/shared/components/data-viewer/types";
import { Svg } from "@/shared/components/display/svg";
import { CodeViewer } from "@/shared/components/editor/code/code-viewer";
import { CsvTable } from "@/shared/components/editor/csv-table";
import { MarkdownViewer } from "@/shared/components/editor/markdown/markdown-viewer";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { classNames } from "@/shared/utils/common";

export interface DataViewerProps {
  data: string;
  contentType?: DataViewerContentType;
  title?: string;
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
  if (isTextContentType(contentType)) {
    return <TextContent contentType={contentType} content={content} />;
  }

  if (isImageContentType(contentType)) {
    return (
      <div className="flex justify-center rounded-lg border border-neutral-700 bg-white p-4">
        <img
          src={`data:${contentType};base64,${content}`}
          alt="Preview"
          className="max-h-150 max-w-full rounded"
        />
      </div>
    );
  }

  if (isPdfContentType(contentType)) {
    return (
      <iframe
        src={`data:application/pdf;base64,${content}`}
        title="PDF Preview"
        className="h-150 w-full rounded-lg border border-neutral-700"
      />
    );
  }

  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-neutral-700 py-12 text-center">
      <p className="text-neutral-400 text-sm">Preview not available for this file type</p>
    </div>
  );
}

function TextContent({ contentType, content }: { contentType: TextContentType; content: string }) {
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

    default:
      return (
        <ScrollArea
          scrollX
          className="grow rounded-lg border border-neutral-700 shadow-sm"
          scrollBarClassName="bg-transparent"
        >
          <CodeViewer language={getLanguage(contentType)} customStyle={{ margin: 0 }}>
            {content}
          </CodeViewer>
        </ScrollArea>
      );
  }
}

function getLanguage(contentType: TextContentType): string {
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
    default:
      return "text";
  }
}

import { type HTMLAttributes, useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";

import { fetchStream } from "@/shared/api/rest/fetch";
import { Svg } from "@/shared/components/display/svg";
import { CodeViewer } from "@/shared/components/editor/code/code-viewer";
import { CsvTable } from "@/shared/components/editor/csv-table";
import { MarkdownViewer } from "@/shared/components/editor/markdown/markdown-viewer";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { classNames } from "@/shared/utils/common";

import type { ArtifactContentType } from "@/entities/artifacts/types";
import { ArtifactFileButton } from "@/entities/artifacts/ui/artifact-file-button";
import { ArtifactFileCopy } from "@/entities/artifacts/ui/artifact-file-copy";
import { ArtifactFileDownload } from "@/entities/artifacts/ui/artifact-file-download";

const CONTENT_TYPE_CONFIG: Record<
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
  "image/svg+xml": { extension: "svg", language: "svg", label: "SVG" },
  "text/plain": { extension: "txt", language: "text", label: "text" },
  "application/xml": { extension: "xml", language: "xml", label: "XML" },
  "text/csv": { extension: "csv", language: "csv", label: "CSV" },
} as const;

function FileLayout({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={classNames(
        "flex grow flex-col gap-2 overflow-auto rounded-lg bg-neutral-800 p-2 text-neutral-200",
        className
      )}
      {...props}
    />
  );
}

export interface FileHeaderProps extends HTMLAttributes<HTMLDivElement> {
  artifactId: string;
  fileContent: string;
  fileUrl: string;
  contentType: ArtifactContentType;
}

function FileHeader({
  artifactId,
  fileContent,
  fileUrl,
  contentType = "text/plain",
  className,
  ...props
}: FileHeaderProps) {
  const config = CONTENT_TYPE_CONFIG[contentType] ?? CONTENT_TYPE_CONFIG["text/plain"];

  return (
    <div className={classNames("flex items-center gap-1", className)} {...props}>
      <span className="grow px-1 font-medium">{config.label}</span>
      <a href={fileUrl} target="_blank" rel="noopener noreferrer">
        <ArtifactFileButton className="leading-4">Raw</ArtifactFileButton>
      </a>
      <ArtifactFileDownload
        contentType={contentType}
        fileName={`${artifactId}.${config.extension}`}
        value={fileContent}
      />
      <ArtifactFileCopy value={fileContent} />
    </div>
  );
}

function FileContent({
  contentType = "text/plain",
  fileContent,
}: {
  contentType: ArtifactContentType;
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

interface ArtifactFileProps {
  artifactId: string;
  url: string;
  contentType: ArtifactContentType;
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

  return (
    <FileLayout>
      <FileHeader
        artifactId={artifactId}
        fileUrl={url}
        fileContent={fileContent}
        contentType={contentType}
      />
      <FileContent contentType={contentType} fileContent={fileContent} />
    </FileLayout>
  );
};

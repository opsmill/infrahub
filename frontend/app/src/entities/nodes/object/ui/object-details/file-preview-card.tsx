import { ExternalLinkIcon } from "lucide-react";

import { Card } from "@/shared/components/ui/card";
import { formatFileSize } from "@/shared/utils/common";
import { getFileIcon } from "@/shared/utils/file";

import type { ArtifactContentType } from "@/entities/artifacts/types";
import { ArtifactFile } from "@/entities/artifacts/ui/artifact-file";

interface FilePreviewCardProps {
  storageId: string;
  fileName: string;
  fileSize?: number;
  contentType?: string;
}

export function FilePreviewCard({
  storageId,
  fileName,
  fileSize,
  contentType,
}: FilePreviewCardProps) {
  const fileUrl = `/api/storage/object/${storageId}`;
  const FileIconComponent = getFileIcon(contentType);

  const artifactContentType = mapToArtifactContentType(contentType);
  const canPreview = artifactContentType || contentType?.startsWith("image/");

  return (
    <Card className="overflow-hidden">
      <div className="border-gray-200 border-b bg-gray-50 p-4">
        <div className="flex items-center gap-2">
          <FileIconComponent className="size-5 shrink-0 text-gray-500" />
          <div className="min-w-0 flex-1">
            <h3 className="truncate font-medium text-gray-900 text-sm">{fileName}</h3>
            {(fileSize || contentType) && (
              <p className="mt-0.5 text-gray-500 text-xs">
                {[fileSize && formatFileSize(fileSize), contentType].filter(Boolean).join(" • ")}
              </p>
            )}
          </div>
          <a
            href={fileUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 rounded px-3 py-1.5 text-custom-blue-600 text-sm hover:bg-gray-100"
          >
            Open
            <ExternalLinkIcon className="size-3.5" />
          </a>
        </div>
      </div>

      <div className="bg-white p-4">
        {canPreview ? (
          <FilePreview
            storageId={storageId}
            fileUrl={fileUrl}
            contentType={contentType}
            artifactContentType={artifactContentType}
            fileName={fileName}
          />
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <FileIconComponent className="mb-3 size-12 text-gray-300" />
            <p className="mb-2 text-gray-600 text-sm">Preview not available for this file type</p>
            <a
              href={fileUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-custom-blue-600 text-sm hover:underline"
            >
              Open file in new tab
              <ExternalLinkIcon className="size-3.5" />
            </a>
          </div>
        )}
      </div>
    </Card>
  );
}

interface FilePreviewProps {
  storageId: string;
  fileUrl: string;
  contentType?: string;
  artifactContentType: ArtifactContentType | null;
  fileName: string;
}

function FilePreview({
  storageId,
  fileUrl,
  contentType,
  artifactContentType,
  fileName,
}: FilePreviewProps) {
  // Images (not handled by ArtifactFile)
  if (contentType?.startsWith("image/") && !contentType.includes("svg")) {
    return (
      <div className="flex justify-center">
        <img src={fileUrl} alt={fileName} className="max-h-150 max-w-full rounded border" />
      </div>
    );
  }

  // PDFs
  if (contentType === "application/pdf") {
    return <iframe src={fileUrl} title={fileName} className="h-150 w-full rounded border" />;
  }

  // Use ArtifactFile for supported types
  if (artifactContentType) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white">
        <ArtifactFile artifactId={storageId} url={fileUrl} contentType={artifactContentType} />
      </div>
    );
  }

  return null;
}

function mapToArtifactContentType(contentType?: string): ArtifactContentType | null {
  if (!contentType) return null;

  const supportedTypes: ArtifactContentType[] = [
    "application/json",
    "application/yaml",
    "application/hcl",
    "image/svg+xml",
    "text/plain",
    "text/markdown",
    "application/xml",
    "text/csv",
  ];

  // Check for exact match
  if (supportedTypes.includes(contentType as ArtifactContentType)) {
    return contentType as ArtifactContentType;
  }

  // Map common variations
  if (contentType === "application/x-yaml") return "application/yaml";
  if (contentType.startsWith("text/")) return "text/plain";

  return null;
}

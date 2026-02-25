import { Link, type LinkProps } from "react-aria-components";

import type { DataViewerContentType } from "@/shared/components/data-viewer/types";

const ALLOWED_URL_SCHEMES = new Set(["http:", "https:", "blob:"]);

function isUrlSafe(url: string): boolean {
  try {
    const parsed = new URL(url, window.location.origin);
    return ALLOWED_URL_SCHEMES.has(parsed.protocol);
  } catch {
    return false;
  }
}

export interface DownloadProps extends Omit<LinkProps, "download" | "href"> {
  contentType?: DataViewerContentType;
  fileName: string;
  downloadUrl?: string;
  data: string;
}

export function Download({
  contentType = "text/plain",
  data,
  fileName,
  downloadUrl,
  ...props
}: DownloadProps) {
  // When a download URL is provided, validate and use it directly
  if (downloadUrl) {
    if (!isUrlSafe(downloadUrl)) {
      console.error(`Download: unsafe URL scheme rejected: ${downloadUrl}`);
      return <Link isDisabled aria-label={`Download ${fileName} (unavailable)`} {...props} />;
    }

    return <Link href={downloadUrl} download={fileName} {...props} />;
  }

  // Otherwise, create a blob from the value
  const blob = new Blob([data], { type: contentType });
  const url = URL.createObjectURL(blob);

  return <Link href={url} download={fileName} {...props} />;
}

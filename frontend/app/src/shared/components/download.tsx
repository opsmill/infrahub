import { Link, type LinkProps } from "react-aria-components";

export interface DownloadProps extends Omit<LinkProps, "download" | "href" | "target" | "rel"> {
  contentType?: string;
  fileName: string;
  /** Direct URL for downloading the file. When provided, uses this URL instead of creating a blob. */
  downloadUrl?: string;
  /** Content value used to create a blob for download when downloadUrl is not provided. */
  value: string;
}

export function Download({
  contentType = "plain/text",
  value,
  fileName,
  downloadUrl,
  ...props
}: DownloadProps) {
  // When a download URL is provided, use it directly
  if (downloadUrl) {
    return (
      <Link
        href={downloadUrl}
        target="_blank"
        rel="noopener noreferrer"
        download={fileName}
        {...props}
      />
    );
  }

  // Otherwise, create a blob from the value
  const blob = new Blob([value], { type: contentType });
  const url = URL.createObjectURL(blob);

  return (
    <Link href={url} target="_blank" rel="noopener noreferrer" download={fileName} {...props} />
  );
}

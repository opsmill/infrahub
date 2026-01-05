import type React from "react";

export interface DownloadProps
  extends Omit<
    React.AnchorHTMLAttributes<HTMLAnchorElement>,
    "download" | "href" | "target" | "rel"
  > {
  contentType?: string;
  fileName: string;
  value: string;
}

export function Download({ contentType = "plain/text", value, fileName, ...props }: DownloadProps) {
  const blob = new Blob([value], { type: contentType });
  const url = URL.createObjectURL(blob);

  return <a href={url} target="_blank" rel="noopener noreferrer" download={fileName} {...props} />;
}

import { Link, type LinkProps } from "react-aria-components";

export interface DownloadProps extends Omit<LinkProps, "download" | "href" | "target" | "rel"> {
  contentType?: string;
  fileName: string;
  value: string;
}

export function Download({ contentType = "plain/text", value, fileName, ...props }: DownloadProps) {
  const blob = new Blob([value], { type: contentType });
  const url = URL.createObjectURL(blob);

  return (
    <Link href={url} target="_blank" rel="noopener noreferrer" download={fileName} {...props} />
  );
}

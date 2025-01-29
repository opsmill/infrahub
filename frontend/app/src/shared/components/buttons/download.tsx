import { Icon } from "@iconify-icon/react";
import { LinkButton, LinkButtonProps } from "./button-primitive";

interface DownloadProps extends Omit<LinkButtonProps, "to"> {
  value: string;
}

export const Download = ({ value, type, ...props }: DownloadProps) => {
  const blob = new Blob([value], { type: type ?? "plain/text" });
  const url = URL.createObjectURL(blob);

  return (
    <LinkButton to={url} target="_blank" rel="noopener noreferrer" {...props}>
      <Icon icon={"mdi:download-outline"} />
    </LinkButton>
  );
};

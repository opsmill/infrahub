import { Icon } from "@iconify-icon/react";
import { LinkButton, LinkButtonProps } from "./button-primitive";

interface DownloadProps extends Omit<LinkButtonProps, "to"> {
  value: string;
}

export const Download = ({ value, ...props }: DownloadProps) => {
  const fileData = JSON.stringify(value);
  const blob = new Blob([fileData], { type: "text/plain" });
  const url = URL.createObjectURL(blob);

  return (
    <LinkButton
      variant={"ghost"}
      size={"icon"}
      to={url}
      target="_blank"
      rel="noopener noreferrer"
      download={"jinja2-template.txt"}
      {...props}
    >
      <Icon icon={"mdi:download-outline"} />
    </LinkButton>
  );
};

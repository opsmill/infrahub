import { MenuItem, type MenuItemProps } from "@infrahub/ui";
import { CopyIcon } from "lucide-react";

import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

export interface CopyToClipboardMenuItemProps extends Omit<MenuItemProps, "onAction" | "children"> {
  textToCopy: string;
  children?: React.ReactNode;
}
export function CopyToClipboardMenuItem({
  textToCopy,
  children,
  ...props
}: CopyToClipboardMenuItemProps) {
  const { copyToClipboard } = useCopyToClipboard();
  return (
    <MenuItem onAction={() => copyToClipboard(textToCopy)} {...props}>
      <CopyIcon className="size-3" />
      {children}
    </MenuItem>
  );
}

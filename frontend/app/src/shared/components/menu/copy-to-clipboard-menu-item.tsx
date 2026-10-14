import { MenuItem, type MenuItemProps } from "@infrahub/ui";
import { CopyIcon } from "lucide-react";

import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

export interface CopyToClipboardMenuItemProps extends Omit<MenuItemProps, "onAction" | "children"> {
  textToCopy: string;
  children?: React.ReactNode;
  onCopy?: (hasCopied: boolean) => void;
}
export function CopyToClipboardMenuItem({
  textToCopy,
  children,
  onCopy,
  ...props
}: CopyToClipboardMenuItemProps) {
  const { copyToClipboard } = useCopyToClipboard();
  return (
    <MenuItem
      onAction={async () => {
        const hasCopied = await copyToClipboard(textToCopy);
        onCopy?.(hasCopied);
      }}
      {...props}
    >
      <CopyIcon className="size-3" />
      {children}
    </MenuItem>
  );
}

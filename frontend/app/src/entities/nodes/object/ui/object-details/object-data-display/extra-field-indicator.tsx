import { EyeIcon } from "lucide-react";

import { classNames } from "@/shared/utils/common";

export function ExtraFieldIndicator({ className }: { className?: string }) {
  return (
    <EyeIcon
      data-testid="extra-field-indicator"
      className={classNames("size-3.5 shrink-0 text-gray-400", className)}
    />
  );
}

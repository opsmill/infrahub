import { Tooltip } from "@infrahub/ui";
import { EyeIcon } from "lucide-react";
import { Focusable } from "react-aria-components";

import { classNames } from "@/shared/utils/common";

export function ExtraFieldIndicator({ className }: { className?: string }) {
  return (
    <Tooltip message="Extra field">
      <Focusable excludeFromTabOrder>
        <EyeIcon
          data-testid="extra-field-indicator"
          onMouseDown={(e) => e.preventDefault()}
          className={classNames("size-3.5 shrink-0 text-gray-400", className)}
        />
      </Focusable>
    </Tooltip>
  );
}

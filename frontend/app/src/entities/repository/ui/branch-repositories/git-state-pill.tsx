import { ColorDisplay } from "@/shared/components/display/color-display";
import { classNames } from "@/shared/utils/common";

import type { BranchRepositorySyncStatus } from "@/entities/repository/domain/model/branch-repository";

interface GitStatePillProps {
  syncStatus: BranchRepositorySyncStatus;
}

export function GitStatePill({ syncStatus }: GitStatePillProps) {
  const { value, label, color, description } = syncStatus;
  // A colour without its label would paint a raw enum value, so the pill falls back to grey.
  const pillColor = label ? color : null;

  return (
    <ColorDisplay
      value={label || value || "—"}
      color={pillColor}
      description={description}
      className={classNames(
        "min-h-0 whitespace-nowrap py-0.5 text-xs",
        !pillColor && "bg-content-strong text-foreground"
      )}
    />
  );
}

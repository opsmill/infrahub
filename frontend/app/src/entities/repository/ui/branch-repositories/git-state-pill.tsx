import { Tooltip } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";
import { getTextColor } from "@/shared/utils/common";

import type { BranchRepositorySyncStatus } from "@/entities/repository/domain/model/branch-repository";

interface GitStatePillProps {
  syncStatus: BranchRepositorySyncStatus;
}

function GitStatePillContent({ syncStatus }: GitStatePillProps) {
  const { value, label, color } = syncStatus;

  if (!label || !color) {
    return (
      <Badge variant="gray" className="whitespace-nowrap font-normal">
        {value || label || "—"}
      </Badge>
    );
  }

  return (
    <span
      className="inline-flex whitespace-nowrap rounded-md px-2 py-0.5 text-xs"
      style={{ backgroundColor: color, color: getTextColor(color) }}
    >
      {label}
    </span>
  );
}

export function GitStatePill({ syncStatus }: GitStatePillProps) {
  return (
    <Tooltip message={syncStatus.description} nonInteractiveTrigger>
      <span className="inline-flex">
        <GitStatePillContent syncStatus={syncStatus} />
      </span>
    </Tooltip>
  );
}

import { Tooltip } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";

import { useConfig } from "@/entities/config/ui/config-provider";
import { instanceBadgeVariant } from "@/entities/preferences/domain/rules/instance-color";

export function InstanceBadge() {
  const { label, color } = useConfig().instance;

  if (!label) return null;

  return (
    <Tooltip message={label} nonInteractiveTrigger>
      <Badge
        variant={instanceBadgeVariant(color)}
        className="inline-block max-w-48 shrink-0 truncate"
        data-testid="instance-badge"
      >
        {label}
      </Badge>
    </Tooltip>
  );
}

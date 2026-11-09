import { Icon } from "@iconify-icon/react";
import { Tooltip } from "@infrahub/ui";

export function BranchGitSyncBadge() {
  return (
    <Tooltip message="Synced with Git" nonInteractiveTrigger>
      <span className="inline-flex shrink-0 items-center justify-center rounded-full bg-custom-blue-700/10 p-1.5 text-custom-blue-700">
        <Icon icon={"mdi:source-branch"} className="size-4" />
      </span>
    </Tooltip>
  );
}

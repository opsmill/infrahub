import { Icon } from "@iconify-icon/react";

import { Tooltip } from "@/shared/components/ui/tooltip";

export function BranchGitSyncBadge() {
  return (
    <Tooltip enabled content="Synced with Git">
      <span className="inline-flex shrink-0 items-center justify-center rounded-full bg-custom-blue-700/10 p-1.5 text-custom-blue-700">
        <Icon icon={"mdi:source-branch"} className="size-4" />
      </span>
    </Tooltip>
  );
}

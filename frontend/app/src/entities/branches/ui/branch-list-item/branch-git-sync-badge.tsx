import { RefreshCwIcon, RefreshCwOffIcon } from "lucide-react";

import { classNames } from "@/shared/utils/common";

export interface BranchGitSyncBadgeProps {
  isSyncWithGit: boolean;
}

const pillStyle =
  "inline-flex shrink-0 items-center gap-1.5 rounded-full border border-transparent px-2 py-1.25 text-xs";

export function BranchGitSyncBadge({ isSyncWithGit }: BranchGitSyncBadgeProps) {
  if (isSyncWithGit) {
    return (
      <span className={classNames(pillStyle, "bg-custom-blue-700/10 text-custom-blue-700")}>
        <RefreshCwIcon className="size-3" /> Synced with Git
      </span>
    );
  }

  return (
    <span className={classNames(pillStyle, "border-gray-300 border-dashed text-gray-500")}>
      <RefreshCwOffIcon className="size-3" /> Not synced
    </span>
  );
}

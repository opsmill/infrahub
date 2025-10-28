import { RefreshCwIcon, RefreshCwOffIcon } from "lucide-react";

export interface BranchGitSyncBadgeProps {
  isSyncWithGit: boolean;
}

export function BranchGitSyncBadge({ isSyncWithGit }: BranchGitSyncBadgeProps) {
  if (isSyncWithGit) {
    return (
      <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-transparent bg-custom-blue-700/10 px-2 py-1.5 text-custom-blue-700 text-xs">
        <RefreshCwIcon className="size-3" /> Synced with Git
      </span>
    );
  }

  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-gray-300 border-dashed px-2 py-1.5 text-gray-500 text-xs">
      <RefreshCwOffIcon className="size-3" /> Not synced
    </span>
  );
}

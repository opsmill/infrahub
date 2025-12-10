import { RefreshCwIcon } from "lucide-react";

export function BranchGitSyncBadge() {
  return (
    <span
      className={
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border border-transparent bg-custom-blue-700/10 px-2 py-1.25 text-custom-blue-700 text-xs"
      }
    >
      <RefreshCwIcon className="size-3" /> Synced with Git
    </span>
  );
}

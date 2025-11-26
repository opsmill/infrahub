import { RefreshCwIcon } from "lucide-react";

import { classNames } from "@/shared/utils/common";

const pillStyle =
  "inline-flex shrink-0 items-center gap-1.5 rounded-full border border-transparent px-2 py-1.25 text-xs";

export function BranchGitSyncBadge() {
  return (
    <span className={classNames(pillStyle, "bg-custom-blue-700/10 text-custom-blue-700")}>
      <RefreshCwIcon className="size-3" /> Synced with Git
    </span>
  );
}

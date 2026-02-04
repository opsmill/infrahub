import { DIFF_TABS } from "@/shared/config/constants";

import { useGetFilesDiff } from "@/entities/diff/domain/get-files-diff.query";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface FilesTabProps {
  sourceBranch: string;
}

export function FilesTab({ sourceBranch }: FilesTabProps) {
  const { isPending, data } = useGetFilesDiff({ branchName: sourceBranch });

  const count = data?.reduce((acc, repo) => acc + (repo.files?.length ?? 0), 0) ?? 0;

  return (
    <ProposedChangeTab
      tabId={DIFF_TABS.FILES}
      label="Files"
      count={count}
      isCountLoading={isPending}
    />
  );
}

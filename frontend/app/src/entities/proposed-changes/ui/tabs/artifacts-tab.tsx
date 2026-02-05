import { DIFF_TABS } from "@/shared/config/constants";

import { useGetArtifactsDiff } from "@/entities/diff/domain/get-artifacts-diff.query";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface ArtifactsTabProps {
  sourceBranch: string;
}

export function ArtifactsTab({ sourceBranch }: ArtifactsTabProps) {
  const { isPending, data, error } = useGetArtifactsDiff({ branch: sourceBranch });

  const count =
    !error && data ? data.filter((artifact) => artifact.action !== "unchanged").length : undefined;

  return (
    <ProposedChangeTab
      tabId={DIFF_TABS.ARTIFACTS}
      label="Artifacts"
      count={count}
      isCountLoading={isPending}
    />
  );
}

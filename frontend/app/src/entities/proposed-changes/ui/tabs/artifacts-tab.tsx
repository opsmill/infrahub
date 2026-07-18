import { useGetArtifactsDiff } from "@/entities/diff/ui/queries/get-artifacts-diff.query";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";
import { getProposedChangeDetailsUrl } from "@/entities/proposed-changes/utils";

export interface ArtifactsTabProps {
  sourceBranch: string;
  proposedChangeId: string;
}

export function ArtifactsTab({ sourceBranch, proposedChangeId }: ArtifactsTabProps) {
  const { isPending, data, error } = useGetArtifactsDiff({ branch: sourceBranch });

  const count =
    !error && data ? data.filter((artifact) => artifact.action !== "unchanged").length : undefined;

  return (
    <ProposedChangeTab
      to={getProposedChangeDetailsUrl(proposedChangeId, "artifacts")}
      label="Artifacts"
      count={count}
      isCountLoading={isPending}
    />
  );
}

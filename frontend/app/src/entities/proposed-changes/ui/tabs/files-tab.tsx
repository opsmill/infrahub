import { useGetFilesDiff } from "@/entities/diff/ui/queries/get-files-diff.query";
import { getProposedChangeDetailsUrl } from "@/entities/proposed-changes/ui/routing/proposed-change-urls";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface FilesTabProps {
  sourceBranch: string;
  proposedChangeId: string;
}

export function FilesTab({ sourceBranch, proposedChangeId }: FilesTabProps) {
  const { isPending, data, error } = useGetFilesDiff({ branchName: sourceBranch });

  const count =
    !error && data ? data.reduce((acc, repo) => acc + (repo.files?.length ?? 0), 0) : undefined;

  return (
    <ProposedChangeTab
      to={getProposedChangeDetailsUrl(proposedChangeId, "files")}
      label="Files"
      count={count}
      isCountLoading={isPending}
    />
  );
}

import { useGetValidatorsQuery } from "@/entities/diff/ui/queries/get-validators.query";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";
import { getProposedChangeDetailsUrl } from "@/entities/proposed-changes/utils";

export interface ChecksTabProps {
  proposedChangeId: string;
}

export function ChecksTab({ proposedChangeId }: ChecksTabProps) {
  const { isPending, data: validators, error } = useGetValidatorsQuery({ proposedChangeId });

  const count = !error && validators ? validators.length : undefined;

  return (
    <ProposedChangeTab
      to={getProposedChangeDetailsUrl(proposedChangeId, "checks")}
      label="Checks"
      count={count}
      isCountLoading={isPending}
    />
  );
}

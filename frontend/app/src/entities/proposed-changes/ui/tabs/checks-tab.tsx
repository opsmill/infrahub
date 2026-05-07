import { useGetValidatorsQuery } from "@/entities/diff/ui/queries/get-validators.query";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface ChecksTabProps {
  proposedChangeId: string;
}

export function ChecksTab({ proposedChangeId }: ChecksTabProps) {
  const { isPending, data: validators, error } = useGetValidatorsQuery({ proposedChangeId });

  const count = !error && validators ? validators.length : undefined;

  return (
    <ProposedChangeTab
      to={`/proposed-changes/${proposedChangeId}/checks`}
      label="Checks"
      count={count}
      isCountLoading={isPending}
    />
  );
}

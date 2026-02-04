import { gql, useQuery } from "@apollo/client";

import { DIFF_TABS, PROPOSED_CHANGES_OBJECT } from "@/shared/config/constants";

import { getProposedChangesChecks } from "@/entities/proposed-changes/api/getProposedChangesChecks";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface ChecksTabProps {
  proposedChangeId: string;
}

export function ChecksTab({ proposedChangeId }: ChecksTabProps) {
  const queryString = getProposedChangesChecks({
    id: proposedChangeId,
    kind: PROPOSED_CHANGES_OBJECT,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, data } = useQuery(query);

  const result = data ? data[PROPOSED_CHANGES_OBJECT]?.edges[0]?.node : {};
  const count = result?.validations?.count ?? 0;

  return (
    <ProposedChangeTab
      tabId={DIFF_TABS.CHECKS}
      label="Checks"
      count={count}
      isCountLoading={loading}
    />
  );
}

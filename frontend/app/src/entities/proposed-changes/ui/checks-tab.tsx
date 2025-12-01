import { gql, useQuery } from "@apollo/client";
import { useParams } from "react-router";

import { Pill } from "@/shared/components/display/pill";
import { PROPOSED_CHANGES_OBJECT } from "@/shared/config/constants";

import { getProposedChangesChecks } from "@/entities/proposed-changes/api/getProposedChangesChecks";

export const ProposedChangesChecksTab = () => {
  const { proposedChangeId } = useParams();

  const queryString = getProposedChangesChecks({
    id: proposedChangeId,
    kind: PROPOSED_CHANGES_OBJECT,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, data } = useQuery(query);

  const result = data ? data[PROPOSED_CHANGES_OBJECT]?.edges[0]?.node : {};

  const validationsCount = result?.validations?.count ?? 0;

  return (
    <div className="ml-2 flex" data-testid="checks-tab">
      <Pill isLoading={loading}>{validationsCount}</Pill>
    </div>
  );
};

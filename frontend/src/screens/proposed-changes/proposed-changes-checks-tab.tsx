import { gql } from "@apollo/client";
import { useParams } from "react-router-dom";
import { Pill } from "../../components/display/pill";
import { PROPOSED_CHANGES_OBJECT } from "../../config/constants";
import { getProposedChangesChecks } from "../../graphql/queries/proposed-changes/getProposedChangesChecks";
import useQuery from "../../hooks/useQuery";

export const ProposedChangesChecksTab = () => {
  const { proposedchange } = useParams();

  const queryString = getProposedChangesChecks({
    id: proposedchange,
    kind: PROPOSED_CHANGES_OBJECT,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, data } = useQuery(query, { pollInterval: 15000 });

  const result = data ? data[PROPOSED_CHANGES_OBJECT]?.edges[0]?.node : {};

  const validationsCount = result?.validations?.count ?? 0;

  return (
    <div className="flex ml-2">
      <Pill isLoading={loading}>{validationsCount}</Pill>
    </div>
  );
};

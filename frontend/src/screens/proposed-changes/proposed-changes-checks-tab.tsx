import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { useParams } from "react-router-dom";
import { Pill } from "../../components/pill";
import { Retry } from "../../components/retry";
import { PROPOSED_CHANGES_OBJECT, VALIDATION_STATES } from "../../config/constants";
import { getProposedChangesChecks } from "../../graphql/queries/proposed-changes/getProposedChangesChecks";
import useQuery from "../../hooks/useQuery";
import { schemaState } from "../../state/atoms/schema.atom";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";

export const ProposedChangesChecksTab = () => {
  const { proposedchange } = useParams();
  const [schemaList] = useAtom(schemaState);
  const schemaData = schemaList.filter((s) => s.name === PROPOSED_CHANGES_OBJECT)[0];

  const queryString = getProposedChangesChecks({
    id: proposedchange,
    kind: schemaData.kind,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data } = useQuery(query, { pollInterval: 1000 });

  if (!schemaData || loading) {
    return <LoadingScreen />;
  }

  if (error) {
    return <ErrorScreen />;
  }

  const result = data ? data[schemaData?.kind]?.edges[0]?.node : {};

  const validationsCount = result?.validations?.count ?? 0;

  const validationsState =
    result?.validations?.edges?.map((edge: any) => edge?.node?.state?.value) ?? [];

  const isInProgress = validationsState.includes(VALIDATION_STATES.IN_PROGRESS);

  return (
    <div className="flex ml-2">
      <Pill>{validationsCount}</Pill>

      {isInProgress && <Retry isInProgress={isInProgress} />}
    </div>
  );
};

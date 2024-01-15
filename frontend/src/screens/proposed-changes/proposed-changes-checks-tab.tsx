import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { useParams } from "react-router-dom";
import { Pill } from "../../components/display/pill";
import { PROPOSED_CHANGES_OBJECT } from "../../config/constants";
import { getProposedChangesChecks } from "../../graphql/queries/proposed-changes/getProposedChangesChecks";
import useQuery from "../../hooks/useQuery";
import { schemaState } from "../../state/atoms/schema.atom";
import LoadingScreen from "../loading-screen/loading-screen";

export const ProposedChangesChecksTab = () => {
  const { proposedchange } = useParams();
  const [schemaList] = useAtom(schemaState);
  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT);

  const queryString = getProposedChangesChecks({
    id: proposedchange,
    kind: schemaData?.kind,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, data } = useQuery(query, { pollInterval: 15000 });

  if (!schemaData || loading) {
    return <LoadingScreen />;
  }

  const result = data ? data[schemaData?.kind]?.edges[0]?.node : {};

  const validationsCount = result?.validations?.count ?? 0;

  return (
    <div className="flex ml-2">
      <Pill>{validationsCount}</Pill>
    </div>
  );
};

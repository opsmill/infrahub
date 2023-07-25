import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { Tabs } from "../../components/tabs";
import { PROPOSED_CHANGES_OBJECT } from "../../config/constants";
import { QSP } from "../../config/qsp";
import { getProposedChanges } from "../../graphql/queries/proposed-changes/getProposedChanges";
import useQuery from "../../hooks/useQuery";
import { schemaState } from "../../state/atoms/schema.atom";
import { getSchemaRelationshipColumns } from "../../utils/getSchemaObjectColumns";
import { DataDiff } from "../branches/diff/data-diff";
import { DIFF_TABS } from "../branches/diff/diff";
import { FilesDiff } from "../branches/diff/files-diff";
import { SchemaDiff } from "../branches/diff/schema-diff";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { Conversations } from "./conversations";

export const PROPOSED_CHANGES_TABS = {
  CONVERSATIONS: "conversations",
};

const tabs = [
  {
    label: "Conversations",
    name: PROPOSED_CHANGES_TABS.CONVERSATIONS,
  },
  {
    label: "Data",
    name: DIFF_TABS.DATA,
  },
  {
    label: "Files",
    name: DIFF_TABS.FILES,
  },
  {
    label: "Schema",
    name: DIFF_TABS.SCHEMA,
  },
];

const renderContent = (tab: string | null | undefined, proposedChangesDetails: any) => {
  switch (tab) {
    case DIFF_TABS.FILES:
      return <FilesDiff proposedChangesDetails={proposedChangesDetails} />;
    case DIFF_TABS.SCHEMA:
      return <SchemaDiff />;
    case DIFF_TABS.DATA:
      return <DataDiff />;
    default: {
      return <Conversations proposedChangesDetails={proposedChangesDetails} />;
    }
  }
};

export const ProposedChangesDetails = () => {
  const { proposedchange } = useParams();
  const [qspTab] = useQueryParam(QSP.PROPOSED_CHANGES_TAB, StringParam);
  const [schemaList] = useAtom(schemaState);

  const schemaData = schemaList.filter((s) => s.name === PROPOSED_CHANGES_OBJECT)[0];

  const queryString = schemaData
    ? getProposedChanges({
        id: proposedchange,
        kind: schemaData.kind,
        attributes: schemaData.attributes,
        relationships: getSchemaRelationshipColumns(schemaData),
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data } = useQuery(query, { skip: !schemaData });

  if (!schemaData || loading) {
    return <LoadingScreen />;
  }

  if (error) {
    return <ErrorScreen />;
  }

  const result = data ? data[schemaData?.kind]?.edges[0]?.node : {};

  return (
    <div>
      <Tabs tabs={tabs} qsp={QSP.PROPOSED_CHANGES_TAB} />

      {renderContent(qspTab, result)}
    </div>
  );
};

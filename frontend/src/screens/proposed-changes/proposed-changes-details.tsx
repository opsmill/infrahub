import { gql } from "@apollo/client";
import { ChevronRightIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { Tabs } from "../../components/tabs";
import { PROPOSED_CHANGES_OBJECT } from "../../config/constants";
import { QSP } from "../../config/qsp";
import { getProposedChanges } from "../../graphql/queries/proposed-changes/getProposedChanges";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";
import { proposedChangedState } from "../../state/atoms/proposedChanges.atom";
import { schemaState } from "../../state/atoms/schema.atom";
import { constructPath } from "../../utils/fetch";
import { getSchemaRelationshipColumns } from "../../utils/getSchemaObjectColumns";
import { ArtifactsDiff } from "../diff/artifact-diff/artifacts-diff";
import { Checks } from "../diff/checks/checks";
import { DataDiff } from "../diff/data-diff";
import { DIFF_TABS } from "../diff/diff";
import { FilesDiff } from "../diff/file-diff/files-diff";
import { SchemaDiff } from "../diff/schema-diff";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { Conversations } from "./conversations";
import { ProposedChangesChecksTab } from "./proposed-changes-checks-tab";

export const PROPOSED_CHANGES_TABS = {
  CONVERSATIONS: "conversations",
};

const renderContent = (tab: string | null | undefined, refetch: any) => {
  switch (tab) {
    case DIFF_TABS.FILES:
      return <FilesDiff />;
    case DIFF_TABS.ARTIFACTS:
      return <ArtifactsDiff />;
    case DIFF_TABS.SCHEMA:
      return <SchemaDiff />;
    case DIFF_TABS.DATA:
      return <DataDiff />;
    case DIFF_TABS.CHECKS:
      return <Checks />;
    default: {
      return <Conversations refetch={refetch} />;
    }
  }
};

export const ProposedChangesDetails = () => {
  const { proposedchange } = useParams();
  const [qspTab] = useQueryParam(QSP.PROPOSED_CHANGES_TAB, StringParam);
  const [, setValidatorQsp] = useQueryParam(QSP.VALIDATOR_DETAILS, StringParam);
  const [schemaList] = useAtom(schemaState);
  const [, setProposedChange] = useAtom(proposedChangedState);
  const navigate = useNavigate();
  useTitle(`${proposedchange} details`);

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT);

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

  const { loading, error, data, refetch } = useQuery(query, { skip: !schemaData });

  if (!schemaData || loading) {
    return <LoadingScreen />;
  }

  if (error) {
    return (
      <ErrorScreen message="Something went wrong when fetching the proposed changes details." />
    );
  }

  const result = data ? data[schemaData?.kind]?.edges[0]?.node : {};

  if (!result) {
    navigate(constructPath("/proposed-changes"));
  }

  setProposedChange(result);

  const tabs = [
    {
      label: "Overview",
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
      label: "Artifacts",
      name: DIFF_TABS.ARTIFACTS,
    },
    {
      label: "Schema",
      name: DIFF_TABS.SCHEMA,
    },
    {
      label: "Checks",
      name: DIFF_TABS.CHECKS,
      // Go back to the validators list when clicking on the tab if we are on the validator details view
      onClick: () => setValidatorQsp(undefined),
      component: ProposedChangesChecksTab,
    },
  ];

  return (
    <>
      <div className="bg-custom-white px-4 py-5 pb-0 sm:px-6 flex items-center">
        <div
          className="text-base font-semibold leading-6 text-gray-900 cursor-pointer hover:underline"
          onClick={() => navigate(constructPath("/proposed-changes"))}>
          Proposed changes
        </div>

        <ChevronRightIcon
          className="w-4 h-4 mt-1 mx-2 flex-shrink-0 text-gray-400"
          aria-hidden="true"
        />

        <p className="mt-1 mr-2 max-w-2xl text-sm text-gray-500">{result?.display_label}</p>
      </div>

      <Tabs tabs={tabs} qsp={QSP.PROPOSED_CHANGES_TAB} />

      {renderContent(qspTab, refetch)}
    </>
  );
};

import { gql } from "@apollo/client";
import { ChevronRightIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useRef } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { Retry } from "../../components/buttons/retry";
import { Tabs } from "../../components/tabs";
import { Link } from "../../components/utils/link";
import { PROPOSED_CHANGES_OBJECT, TASK_OBJECT, TASK_TAB } from "../../config/constants";
import { QSP } from "../../config/qsp";
import { getProposedChanges } from "../../graphql/queries/proposed-changes/getProposedChanges";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";
import { proposedChangedState } from "../../state/atoms/proposedChanges.atom";
import { schemaState } from "../../state/atoms/schema.atom";
import { constructPath } from "../../utils/fetch";
import { getObjectRelationships } from "../../utils/getSchemaObjectColumns";
import { ArtifactsDiff } from "../diff/artifact-diff/artifacts-diff";
import { Checks } from "../diff/checks/checks";
import { DataDiff } from "../diff/data-diff";
import { DIFF_TABS } from "../diff/diff";
import { FilesDiff } from "../diff/file-diff/files-diff";
import { SchemaDiff } from "../diff/schema-diff";
import ErrorScreen from "../error-screen/error-screen";
import { TaskItemDetails } from "../tasks/task-item-details";
import { TaskItems } from "../tasks/task-items";
import { Conversations } from "./conversations";
import { ProposedChangesChecksTab } from "./proposed-changes-checks-tab";

export const PROPOSED_CHANGES_TABS = {
  CONVERSATIONS: "conversations",
};

export const ProposedChangesDetails = () => {
  const { proposedchange } = useParams();
  const location = useLocation();
  const { pathname } = location;
  const [qspTab, setQspTab] = useQueryParam(QSP.PROPOSED_CHANGES_TAB, StringParam);
  const [qspTaskId, setQspTaskId] = useQueryParam(QSP.TASK_ID, StringParam);
  const [, setValidatorQsp] = useQueryParam(QSP.VALIDATOR_DETAILS, StringParam);
  const [schemaList] = useAtom(schemaState);
  const [proposedChange, setProposedChange] = useAtom(proposedChangedState);
  const navigate = useNavigate();
  useTitle(
    proposedChange?.display_label
      ? `${proposedChange.display_label} details`
      : "Proposed changes details"
  );
  const refetchRef = useRef(null);

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT);
  const relationships = getObjectRelationships(schemaData);

  const queryString = schemaData
    ? getProposedChanges({
        id: proposedchange,
        kind: schemaData.kind,
        attributes: schemaData.attributes,
        relationships,
        taskKind: TASK_OBJECT,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data, refetch } = useQuery(query, {
    skip: !schemaData,
    notifyOnNetworkStatusChange: true,
  });

  // TODO: refactor to not need the ref to refetch child query
  const handleRefetch = () => {
    refetch();
    if (refetchRef?.current?.refetch) {
      refetchRef?.current?.refetch();
    }
  };

  if (error) {
    return (
      <ErrorScreen message="Something went wrong when fetching the proposed changes details." />
    );
  }

  const result = data && data[schemaData?.kind]?.edges[0]?.node;

  if (result) setProposedChange(result);

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
    {
      label: "Tasks",
      name: TASK_TAB,
      count: data[TASK_OBJECT]?.count ?? 0,
      onClick: () => {
        setQspTab(TASK_TAB);
        setQspTaskId(undefined);
      },
    },
  ];

  const renderContent = () => {
    switch (qspTab) {
      case DIFF_TABS.FILES:
        return <FilesDiff ref={refetchRef} />;
      case DIFF_TABS.ARTIFACTS:
        return <ArtifactsDiff ref={refetchRef} />;
      case DIFF_TABS.SCHEMA:
        return <SchemaDiff ref={refetchRef} />;
      case DIFF_TABS.DATA:
        return <DataDiff ref={refetchRef} />;
      case DIFF_TABS.CHECKS:
        return <Checks ref={refetchRef} />;
      case TASK_TAB:
        if (!qspTaskId) return <TaskItems ref={refetchRef} />;

        return (
          <div>
            <div className="flex bg-custom-white text-sm">
              <Link
                to={constructPath(pathname, [
                  { name: QSP.PROPOSED_CHANGES_TAB, value: TASK_TAB },
                  { name: QSP.TASK_ID, exclude: true },
                ])}
                className="flex items-center p-2 ">
                <Icon icon={"mdi:chevron-left"} />
                All tasks
              </Link>
            </div>

            <TaskItemDetails ref={refetchRef} />
          </div>
        );
      default: {
        return <Conversations refetch={refetch} ref={refetchRef} />;
      }
    }
  };

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

        <div className="ml-2">
          <Retry isLoading={loading} onClick={handleRefetch} />
        </div>
      </div>

      <Tabs tabs={tabs} qsp={QSP.PROPOSED_CHANGES_TAB} />

      {renderContent()}
    </>
  );
};

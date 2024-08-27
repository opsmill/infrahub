import { Tabs } from "@/components/tabs";
import { Link } from "@/components/ui/link";
import { DIFF_TABS, PROPOSED_CHANGES_OBJECT, TASK_OBJECT, TASK_TAB } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { GET_PROPOSED_CHANGE_DETAILS } from "@/graphql/queries/proposed-changes/getProposedChangesDetails";
import useQuery from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import { ArtifactsDiff } from "@/screens/diff/artifact-diff/artifacts-diff";
import { Checks } from "@/screens/diff/checks/checks";
import { NodeDiff } from "@/screens/diff/node-diff";

import { FilesDiff } from "@/screens/diff/file-diff/files-diff";
import ErrorScreen from "@/screens/errors/error-screen";
import Content from "@/screens/layout/content";
import { TaskItemDetails } from "@/screens/tasks/task-item-details";
import { TaskItems } from "@/screens/tasks/task-items";
import { proposedChangedState } from "@/state/atoms/proposedChanges.atom";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { Navigate, useLocation, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { ProposedChangesChecksTab } from "@/screens/proposed-changes/checks-tab";
import { ProposedChangeDetails } from "@/screens/proposed-changes/proposed-change-details";
import { Conversations } from "@/screens/proposed-changes/conversations";
import { NetworkStatus } from "@apollo/client";
import { CoreProposedChange } from "@/generated/graphql";

export const PROPOSED_CHANGES_TABS = {
  CONVERSATIONS: "conversations",
};

interface ProposedChangesDetailsPageProps {
  proposedChangeData: CoreProposedChange;
}

const ProposedChangeDetailsContent = ({ proposedChangeData }: ProposedChangesDetailsPageProps) => {
  const { pathname } = useLocation();
  const [qspTab] = useQueryParam(QSP.PROPOSED_CHANGES_TAB, StringParam);
  const [qspTaskId] = useQueryParam(QSP.TASK_ID, StringParam);
  const [proposedChange, setProposedChange] = useAtom(proposedChangedState);
  useTitle(
    `${
      proposedChange.display_label ? `${proposedChange.display_label} - ` : ""
    }Proposed change - Infrahub`
  );

  if (proposedChangeData) setProposedChange(proposedChangeData);

  switch (qspTab) {
    case DIFF_TABS.FILES:
      return <FilesDiff />;
    case DIFF_TABS.ARTIFACTS:
      return <ArtifactsDiff />;
    case DIFF_TABS.SCHEMA:
      return (
        <NodeDiff
          filters={{
            namespace: { includes: ["Schema"], excludes: ["Profile"] },
            status: { excludes: ["UNCHANGED"] },
          }}
        />
      );
    case DIFF_TABS.DATA:
      return (
        <NodeDiff
          filters={{
            namespace: { excludes: ["Schema", "Profile"] },
            status: { excludes: ["UNCHANGED"] },
          }}
        />
      );
    case DIFF_TABS.CHECKS:
      return <Checks />;
    case TASK_TAB:
      if (!qspTaskId) return <TaskItems hideRelatedNode />;

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

          <TaskItemDetails />
        </div>
      );
    default: {
      return (
        <div className="flex flex-wrap p-2 gap-2 items-start">
          <ProposedChangeDetails />

          <Conversations />
        </div>
      );
    }
  }
};

export function Component() {
  const { proposedChangeId } = useParams();

  const { loading, networkStatus, error, data, client } = useQuery(GET_PROPOSED_CHANGE_DETAILS, {
    notifyOnNetworkStatusChange: true,
    variables: {
      id: proposedChangeId,
      nodeId: proposedChangeId, // Used for tasks, which is a different type
    },
  });

  if (networkStatus === NetworkStatus.loading) {
    return <LoadingScreen className="m-auto h-auto" />;
  }

  if (error) {
    return (
      <ErrorScreen message="Something went wrong when fetching the proposed changes details." />
    );
  }

  const proposedChangesData = data?.[PROPOSED_CHANGES_OBJECT]?.edges?.[0]?.node;
  console.log("proposedChangesData: ", proposedChangesData);

  if (!proposedChangesData) {
    return <Navigate to={constructPath("/proposed-changes")} />;
  }

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
      component: ProposedChangesChecksTab,
    },
    {
      label: "Tasks",
      name: TASK_TAB,
      count: (data && data[TASK_OBJECT]?.count) ?? 0,
    },
  ];

  return (
    <Content>
      <Content.Title
        title={
          <div className="flex items-center gap-2">
            <Link className="no-underline hover:underline" to={constructPath("/proposed-changes")}>
              Proposed changes
            </Link>

            <Icon icon="mdi:chevron-right" />

            <span>{proposedChangesData.display_label}</span>
          </div>
        }
        reload={() => client.reFetchObservableQueries()}
        isReloadLoading={loading}
      />

      <Tabs tabs={tabs} qsp={QSP.PROPOSED_CHANGES_TAB} />

      <ProposedChangeDetailsContent proposedChangeData={proposedChangesData} />
    </Content>
  );
}

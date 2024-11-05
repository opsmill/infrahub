import { Tabs } from "@/components/tabs";
import { DIFF_TABS, PROPOSED_CHANGES_OBJECT, TASK_OBJECT, TASK_TAB } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { GET_PROPOSED_CHANGE_DETAILS } from "@/graphql/queries/proposed-changes/getProposedChangesDetails";
import useQuery from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import { ArtifactsDiff } from "@/screens/diff/artifact-diff/artifacts-diff";
import { Checks } from "@/screens/diff/checks/checks";
import { NodeDiff } from "@/screens/diff/node-diff";

import { ObjectHelpButton } from "@/components/menu/object-help-button";
import { Badge } from "@/components/ui/badge";
import { CoreProposedChange } from "@/generated/graphql";
import { useSchema } from "@/hooks/useSchema";
import { FilesDiff } from "@/screens/diff/file-diff/files-diff";
import ErrorScreen from "@/screens/errors/error-screen";
import NoDataFound from "@/screens/errors/no-data-found";
import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { ProposedChangesChecksTab } from "@/screens/proposed-changes/checks-tab";
import { ProposedChangeDetails } from "@/screens/proposed-changes/proposed-change-details";
import { TaskItemDetails } from "@/screens/tasks/task-item-details";
import { TaskItems } from "@/screens/tasks/task-items";
import { proposedChangedState } from "@/state/atoms/proposedChanges.atom";
import { constructPath } from "@/utils/fetch";
import { getObjectDetailsUrl } from "@/utils/objects";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { Link, useLocation, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";

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
              className="flex items-center p-2 "
            >
              <Icon icon={"mdi:chevron-left"} />
              All tasks
            </Link>
          </div>

          <TaskItemDetails />
        </div>
      );
    default: {
      return <ProposedChangeDetails />;
    }
  }
};

export function Component() {
  const { proposedChangeId } = useParams();
  const { schema } = useSchema(PROPOSED_CHANGES_OBJECT);

  const { loading, error, data, client } = useQuery(GET_PROPOSED_CHANGE_DETAILS, {
    variables: {
      id: proposedChangeId,
      nodeId: proposedChangeId, // Used for tasks, which is a different type
    },
  });

  if (loading) {
    return <LoadingScreen className="m-auto h-auto" />;
  }

  const proposedChangesData = data?.[PROPOSED_CHANGES_OBJECT]?.edges?.[0]?.node;

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

  if (error || !proposedChangesData) {
    return (
      <Content.Card>
        <Content.CardTitle
          title="Proposed changes"
          reload={() => client.reFetchObservableQueries()}
          isReloadLoading={loading}
          end={
            <ObjectHelpButton
              documentationUrl={schema?.documentation}
              kind={PROPOSED_CHANGES_OBJECT}
              className="ml-auto"
            />
          }
        />

        {error && (
          <ErrorScreen message="Something went wrong when fetching the proposed changes details." />
        )}

        {!proposedChangesData && <NoDataFound message="No proposed changes found." />}
      </Content.Card>
    );
  }

  return (
    <Content.Card className="min-h-[calc(100%-1rem)] flex flex-col">
      <Content.CardTitle
        title={proposedChangesData.display_label}
        description={
          <div className="inline-flex gap-1 text-xs items-center">
            <Link
              to={constructPath(
                getObjectDetailsUrl(
                  proposedChangesData?.created_by?.node?.id,
                  proposedChangesData?.created_by?.node?.__typename
                )
              )}
              className="font-semibold text-custom-blue-green"
            >
              {proposedChangesData?.created_by?.node?.display_label}
            </Link>
            wants to merge
            <Link to={constructPath(`/branches/${proposedChangesData.source_branch?.value}`)}>
              <Badge variant="blue">
                <Icon icon="mdi:layers-triple" className="mr-1" />
                {proposedChangesData.source_branch?.value}
              </Badge>
            </Link>
            into
            <Link to={constructPath(`/branches/${proposedChangesData.destination_branch?.value}`)}>
              <Badge variant="green" className="items-center">
                <Icon icon="mdi:layers-triple" className="mr-1" />
                {proposedChangesData.destination_branch?.value}
              </Badge>
            </Link>
          </div>
        }
        reload={() => client.reFetchObservableQueries()}
        isReloadLoading={loading}
        end={
          <ObjectHelpButton
            documentationUrl={schema?.documentation}
            kind={PROPOSED_CHANGES_OBJECT}
            className="ml-auto"
          />
        }
      />

      <Tabs tabs={tabs} qsp={QSP.PROPOSED_CHANGES_TAB} />

      <ProposedChangeDetailsContent proposedChangeData={proposedChangesData} />
    </Content.Card>
  );
}

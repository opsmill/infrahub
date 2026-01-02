import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useQueryState } from "nuqs";
import { Link, useLocation, useParams } from "react-router";

import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Tabs } from "@/shared/components/tabs";
import { Badge } from "@/shared/components/ui/badge";
import { DIFF_TABS, PROPOSED_CHANGES_OBJECT, TASK_TAB } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";
import { useTitle } from "@/shared/hooks/useTitle";

import { ArtifactsDiff } from "@/entities/diff/artifact-diff/artifacts-diff";
import { Checks } from "@/entities/diff/checks/checks";
import { FilesDiff } from "@/entities/diff/file-diff/files-diff";
import { NodeDiff } from "@/entities/diff/node-diff";
import { ObjectHelpButton } from "@/entities/nodes/object/ui/object-help-button";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { GetProposedChangeDetailsResponse } from "@/entities/proposed-changes/domain/get-proposed-change-details";
import { useGetProposedChangeDetails } from "@/entities/proposed-changes/domain/get-proposed-change-details.query";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { ProposedChangesChecksTab } from "@/entities/proposed-changes/ui/checks-tab";
import { ProposedChangeDetails } from "@/entities/proposed-changes/ui/proposed-change-details";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { TaskItemDetails } from "@/entities/tasks/ui/task-item-details";
import { TaskItems } from "@/entities/tasks/ui/task-items";

export const PROPOSED_CHANGES_TABS = {
  CONVERSATIONS: "conversations",
};

const ProposedChangeDetailsContent = (props: GetProposedChangeDetailsResponse) => {
  const { proposedChangeData } = props;
  const { pathname } = useLocation();
  const [qspTab] = useQueryState(QSP.PROPOSED_CHANGES_TAB);
  const [qspTaskId] = useQueryState(QSP.TASK_ID);
  const [proposedChange, setProposedChange] = useAtom(proposedChangedState);
  useTitle(
    `${proposedChange ? `${getNodeLabel(proposedChange)} - ` : ""}Proposed change - Infrahub`
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
          <div className="flex bg-white text-sm">
            <Link
              to={constructPath(pathname, [
                { name: QSP.PROPOSED_CHANGES_TAB, value: TASK_TAB },
                { name: QSP.TASK_ID, exclude: true },
              ])}
              className="flex items-center p-2"
            >
              <Icon icon={"mdi:chevron-left"} />
              All tasks
            </Link>
          </div>

          <TaskItemDetails />
        </div>
      );
    default: {
      return <ProposedChangeDetails {...props} />;
    }
  }
};

export function Component() {
  const { proposedChangeId } = useParams() as { proposedChangeId: string };
  const { schema } = useSchema(PROPOSED_CHANGES_OBJECT);

  const { isPending, error, data } = useGetProposedChangeDetails({ proposedChangeId });

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  const { proposedChangeData, tasksCount, metadata } = data ?? {};

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
      count: tasksCount ?? 0,
    },
  ];

  if (error || !proposedChangeData) {
    return (
      <Content.Card>
        <Content.CardTitle
          title="Proposed changes"
          reload={() => {
            queryClient.invalidateQueries({
              predicate: (query) => query.queryKey.includes(proposedChangeId),
            });
          }}
          isReloadLoading={isPending}
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

        {!proposedChangeData && <NoDataFound message="No proposed changes found." />}
      </Content.Card>
    );
  }

  return (
    <Content.Card className="flex flex-col">
      <Content.CardTitle
        title={getNodeLabel(proposedChangeData)}
        description={
          <div className="inline-flex items-center gap-1 text-xs">
            <Link
              to={getObjectDetailsUrl(metadata?.created_by?.__typename, metadata?.created_by?.id)}
              className="font-semibold text-custom-blue-green"
            >
              {metadata?.created_by ? getNodeLabel(metadata.created_by) : ""}
            </Link>
            wants to merge
            <Link to={constructPath(`/branches/${proposedChangeData.source_branch?.value}`)}>
              <Badge variant="blue">
                <Icon icon="mdi:layers-triple" className="mr-1" />
                {proposedChangeData.source_branch?.value}
              </Badge>
            </Link>
            into
            <Link to={constructPath(`/branches/${proposedChangeData.destination_branch?.value}`)}>
              <Badge variant="green" className="items-center">
                <Icon icon="mdi:layers-triple" className="mr-1" />
                {proposedChangeData.destination_branch?.value}
              </Badge>
            </Link>
          </div>
        }
        reload={() => {
          queryClient.invalidateQueries({
            predicate: (query) => query.queryKey.includes(proposedChangeId),
          });
        }}
        isReloadLoading={isPending}
        end={
          <ObjectHelpButton
            documentationUrl={schema?.documentation}
            kind={PROPOSED_CHANGES_OBJECT}
            className="ml-auto"
          />
        }
      />

      <Tabs tabs={tabs} qsp={QSP.PROPOSED_CHANGES_TAB} />

      <ProposedChangeDetailsContent {...data} />
    </Content.Card>
  );
}

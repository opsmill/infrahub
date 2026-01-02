import { Icon } from "@iconify-icon/react";
import type { HTMLAttributes } from "react";
import { useNavigate, useParams } from "react-router";

import useQuery from "@/shared/api/graphql/useQuery";
import { constructPath } from "@/shared/api/rest/fetch";
import Accordion from "@/shared/components/display/accordion";
import { Avatar } from "@/shared/components/display/avatar";
import { DateDisplay } from "@/shared/components/display/date-display";
import { MarkdownRender } from "@/shared/components/editor/markdown/markdown-render";
import { type Property, PropertyList } from "@/shared/components/table/property-list";
import { Badge } from "@/shared/components/ui/badge";
import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { TASK_OBJECT } from "@/shared/config/constants";
import { classNames } from "@/shared/utils/common";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { GetProposedChangeDetailsResponse } from "@/entities/proposed-changes/domain/get-proposed-change-details";
import { PcActionButton } from "@/entities/proposed-changes/ui/action-button/pc-action-button";
import { PcReviewButton } from "@/entities/proposed-changes/ui/action-button/pc-review-button";
import { Overview } from "@/entities/proposed-changes/ui/overview";
import { ProposedChangeEditTrigger } from "@/entities/proposed-changes/ui/proposed-change-edit-trigger";
import { getProposedChangesStateBadgeType } from "@/entities/proposed-changes/utils/proposed-changes";
import { TASK_DETAILS_CHECK } from "@/entities/tasks/api/checkTasksItemDetails";
import { PROPOSED_CHANGE_MERGE_WORKFLOW, TASK_ONGOING_STATES } from "@/entities/tasks/constants";
import { TaskDisplay } from "@/entities/tasks/ui/task-display";

interface ProposedChangeDetailsProps
  extends HTMLAttributes<HTMLDivElement>,
    GetProposedChangeDetailsResponse {}

export const ProposedChangeDetails = ({
  proposedChangeData,
  metadata,
  tasksCount,
  className,
  ...props
}: ProposedChangeDetailsProps) => {
  const { proposedChangeId } = useParams();
  const navigate = useNavigate();

  const { loading: loadingCheck, data: checkData } = useQuery(TASK_DETAILS_CHECK, {
    variables: {
      workflow: [PROPOSED_CHANGE_MERGE_WORKFLOW],
      state: TASK_ONGOING_STATES,
      relatedNodes: proposedChangeId ? [proposedChangeId] : undefined,
    },
    pollInterval: 10_000,
  });

  const rejectedBy = proposedChangeData?.rejected_by?.edges?.map((edge) => edge.node) ?? [];
  const approvedBy = proposedChangeData?.approved_by?.edges?.map((edge) => edge.node) ?? [];
  const reviewers = proposedChangeData?.reviewers?.edges?.map((edge) => edge.node) ?? [];

  const path = constructPath("/proposed-changes");
  const state = proposedChangeData?.state?.value;
  const isDraft = proposedChangeData?.is_draft?.value;

  const proposedChangeProperties: Property[] = [
    {
      name: "ID",
      value: proposedChangeData.id,
    },
    {
      name: "State",
      value: (
        <>
          <Badge variant={getProposedChangesStateBadgeType(state)}>{state}</Badge>

          {isDraft && (
            <Badge variant={"gray"} className="ml-2">
              draft
            </Badge>
          )}
        </>
      ),
    },
    {
      name: "Source branch",
      value: (
        <Badge variant="blue">
          <Icon icon="mdi:layers-triple" className="mr-1" />
          {proposedChangeData?.source_branch?.value}
        </Badge>
      ),
    },
    {
      name: "Destination branch",
      value: (
        <Badge variant="green">
          <Icon icon="mdi:layers-triple" className="mr-1" />
          {proposedChangeData?.destination_branch?.value}
        </Badge>
      ),
    },
    {
      name: "Created by",
      value: metadata.created_by ? (
        <Tooltip content={getNodeLabel(metadata.created_by)} enabled>
          <Avatar
            size={"sm"}
            name={getNodeLabel(metadata.created_by)}
            className="bg-custom-blue-green"
          />
        </Tooltip>
      ) : (
        "-"
      ),
    },
    {
      name: "Created at",
      value: <DateDisplay date={metadata.created_at} />,
    },
    {
      name: "Updated by",
      value: metadata.updated_by ? (
        <Tooltip content={getNodeLabel(metadata.updated_by)} enabled>
          <Avatar
            size="sm"
            name={getNodeLabel(metadata.updated_by)}
            className="bg-custom-blue-green"
          />
        </Tooltip>
      ) : (
        "-"
      ),
    },
    {
      name: "Updated at",
      value: <DateDisplay date={metadata.updated_at} />,
    },
    {
      name: "Reviewers",
      value: (
        <div className="flex flex-wrap gap-2">
          {reviewers.map((reviewer: any, index: number) => (
            <Tooltip key={index} content={getNodeLabel(reviewer)} enabled>
              <Avatar size={"sm"} name={getNodeLabel(reviewer)} />
            </Tooltip>
          ))}
        </div>
      ),
    },
    {
      name: "Approved by",
      value: (
        <div className="flex flex-wrap gap-2">
          {approvedBy.map((user: any, index: number) => (
            <Tooltip key={index} content={getNodeLabel(user)} enabled>
              <Avatar size={"sm"} name={getNodeLabel(user)} />
            </Tooltip>
          ))}
        </div>
      ),
    },
    {
      name: "Rejected by",
      value: (
        <div className="flex flex-wrap gap-2">
          {rejectedBy.map((user: any, index: number) => (
            <Tooltip key={index} content={getNodeLabel(user)} enabled>
              <Avatar size={"sm"} name={getNodeLabel(user)} />
            </Tooltip>
          ))}
        </div>
      ),
    },
  ];

  return (
    <div className="flex grow flex-col gap-2.5 bg-stone-50 p-2.5">
      {!loadingCheck && checkData && !!checkData[TASK_OBJECT].count && (
        <Card>
          <Accordion title={<div className="font-normal text-xs">Actions in progress</div>}>
            <div className="mt-2">
              <TaskDisplay
                relatedNode={proposedChangeId}
                workflow={[PROPOSED_CHANGE_MERGE_WORKFLOW]}
              />
            </div>
          </Accordion>
        </Card>
      )}

      <div className={classNames("grid grid-cols-3 items-start gap-2", className)} {...props}>
        <div className="col-start-1 col-end-3 space-y-2">
          {proposedChangeData?.description?.value && (
            <CardWithBorder contentClassName="" data-testid="pc-description">
              <CardWithBorder.Title className="flex items-center gap-2">
                <Avatar
                  name={metadata.created_by ? getNodeLabel(metadata.created_by) : ""}
                  size="sm"
                />

                {metadata.created_by ? getNodeLabel(metadata.created_by) : ""}

                <DateDisplay
                  date={proposedChangeData.description.updated_at}
                  className="ml-auto font-normal text-gray-600 text-xs"
                />
              </CardWithBorder.Title>

              <MarkdownRender markdownText={proposedChangeData.description.value} className="m-2" />
            </CardWithBorder>
          )}

          <Overview />
        </div>

        <CardWithBorder className="col-start-3 col-end-4 min-w-[300px]">
          <CardWithBorder.Title className="flex items-center justify-between">
            <div
              onClick={() => navigate(path)}
              className="cursor-pointer font-semibold text-base text-gray-900 leading-6 hover:underline"
            >
              Proposed change
            </div>

            <ProposedChangeEditTrigger proposedChangesDetails={proposedChangeData} />
          </CardWithBorder.Title>

          <PropertyList properties={proposedChangeProperties} />

          <div className="flex grow gap-2 p-2">
            <PcReviewButton />
            <PcActionButton />
          </div>
        </CardWithBorder>
      </div>
    </div>
  );
};

import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import type { HTMLAttributes } from "react";
import { useNavigate, useParams } from "react-router";

import { TASK_OBJECT } from "@/config/constants";

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
import { classNames } from "@/shared/utils/common";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { PcActionButton } from "@/entities/proposed-changes/ui/action-button/pc-action-button";
import { PcReviewButton } from "@/entities/proposed-changes/ui/action-button/pc-review-button";
import { Overview } from "@/entities/proposed-changes/ui/overview";
import { ProposedChangeEditTrigger } from "@/entities/proposed-changes/ui/proposed-change-edit-trigger";
import { getProposedChangesStateBadgeType } from "@/entities/proposed-changes/utils/proposed-changes";
import { TASK_DETAILS_CHECK } from "@/entities/tasks/api/checkTasksItemDetails";
import { PROPOSED_CHANGE_MERGE_WORKFLOW, TASK_ONGOING_STATES } from "@/entities/tasks/constants";
import { TaskDisplay } from "@/entities/tasks/ui/task-display";

export const ProposedChangeDetails = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => {
  const { proposedChangeId } = useParams();
  const proposedChangesDetails = useAtomValue(proposedChangedState);

  const navigate = useNavigate();

  const { loading: loadingCheck, data: checkData } = useQuery(TASK_DETAILS_CHECK, {
    variables: {
      workflow: [PROPOSED_CHANGE_MERGE_WORKFLOW],
      state: TASK_ONGOING_STATES,
      relatedNodes: proposedChangeId ? [proposedChangeId] : undefined,
    },
    pollInterval: 10_000,
  });

  const rejectedBy = proposedChangesDetails?.rejected_by?.edges.map((edge: any) => edge.node) ?? [];
  const approvedBy = proposedChangesDetails?.approved_by?.edges.map((edge: any) => edge.node) ?? [];
  const reviewers = proposedChangesDetails?.reviewers?.edges.map((edge: any) => edge.node) ?? [];

  const path = constructPath("/proposed-changes");
  const state = proposedChangesDetails?.state?.value;
  const isDraft = proposedChangesDetails?.is_draft?.value;

  const proposedChangeProperties: Property[] = [
    {
      name: "ID",
      value: proposedChangesDetails.id,
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
          {proposedChangesDetails?.source_branch?.value}
        </Badge>
      ),
    },
    {
      name: "Destination branch",
      value: (
        <Badge variant="green">
          <Icon icon="mdi:layers-triple" className="mr-1" />
          {proposedChangesDetails?.destination_branch?.value}
        </Badge>
      ),
    },
    {
      name: "Created by",
      value: (
        <Tooltip content={proposedChangesDetails?.created_by?.node ? getNodeLabel(proposedChangesDetails.created_by.node) : ""} enabled>
          <Avatar
            size={"sm"}
            name={proposedChangesDetails?.created_by?.node ? getNodeLabel(proposedChangesDetails.created_by.node) : ""}
            className="bg-custom-blue-green"
          />
        </Tooltip>
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
      name: "Updated",
      value: <DateDisplay date={proposedChangesDetails?._updated_at} />,
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
          {proposedChangesDetails?.description?.value && (
            <CardWithBorder contentClassName="" data-testid="pc-description">
              <CardWithBorder.Title className="flex items-center gap-2">
                <Avatar name={proposedChangesDetails?.created_by?.node ? getNodeLabel(proposedChangesDetails.created_by.node) : ""} size="sm" />

                {proposedChangesDetails?.created_by?.node ? getNodeLabel(proposedChangesDetails.created_by.node) : ""}

                <DateDisplay
                  date={proposedChangesDetails.description.updated_at}
                  className="ml-auto font-normal text-gray-600 text-xs"
                />
              </CardWithBorder.Title>

              <MarkdownRender
                markdownText={proposedChangesDetails.description.value}
                className="m-2"
              />
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

            <ProposedChangeEditTrigger proposedChangesDetails={proposedChangesDetails} />
          </CardWithBorder.Title>

          <PropertyList properties={proposedChangeProperties} />

          <div className="flex flex-grow gap-2 p-2">
            <PcReviewButton />
            <PcActionButton />
          </div>
        </CardWithBorder>
      </div>
    </div>
  );
};

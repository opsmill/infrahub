import { TASK_OBJECT } from "@/config/constants";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { PcActionButton } from "@/entities/proposed-changes/ui/action-button/pc-actions-button";
import { Overview } from "@/entities/proposed-changes/ui/overview";
import { ProposedChangeEditTrigger } from "@/entities/proposed-changes/ui/proposed-change-edit-trigger";
import { getProposedChangesStateBadgeType } from "@/entities/proposed-changes/utils/proposed-changes";
import { TASK_DETAILS_CHECK } from "@/entities/tasks/api/checkTasksItemDetails";
import useQuery from "@/shared/api/graphql/useQuery";
import { constructPath } from "@/shared/api/rest/fetch";
import Accordion from "@/shared/components/display/accordion";
import { Avatar } from "@/shared/components/display/avatar";
import { DateDisplay } from "@/shared/components/display/date-display";
import { MarkdownRender } from "@/shared/components/editor/markdown/markdown-render";
import { Property, PropertyList } from "@/shared/components/table/property-list";
import { Badge } from "@/shared/components/ui/badge";
import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { HTMLAttributes } from "react";
import { useNavigate, useParams } from "react-router";
import { PROPOSED_CHANGE_MERGE_WORKFLOW, TASK_ONGOING_STATES } from "../../tasks/constants";
import { TaskDisplay } from "../../tasks/ui/task-display";

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
    pollInterval: 2000,
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
        <Tooltip content={proposedChangesDetails?.created_by?.node?.display_label} enabled>
          <Avatar
            size={"sm"}
            name={proposedChangesDetails?.created_by?.node?.display_label}
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
            <Tooltip key={index} content={user.display_label} enabled>
              <Avatar size={"sm"} name={user.display_label} />
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
            <Tooltip key={index} content={user.display_label} enabled>
              <Avatar size={"sm"} name={user.display_label} />
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
            <Tooltip key={index} content={reviewer.display_label} enabled>
              <Avatar size={"sm"} name={reviewer.display_label} />
            </Tooltip>
          ))}
        </div>
      ),
    },
    {
      name: "Updated",
      value: <DateDisplay date={proposedChangesDetails?._updated_at} />,
    },
    {
      name: "Actions",
      value: (
        <div className="flex flex-wrap gap-2">
          <PcActionButton />
        </div>
      ),
    },
  ];

  return (
    <div className="bg-stone-50 p-2.5 flex flex-col grow gap-2.5">
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

      <div className={classNames("grid grid-cols-3 gap-2", className)} {...props}>
        <div className="col-start-1 col-end-3 space-y-2">
          {proposedChangesDetails?.description?.value && (
            <CardWithBorder contentClassName="" data-testid="pc-description">
              <CardWithBorder.Title className="flex gap-2 items-center">
                <Avatar name={proposedChangesDetails?.created_by?.node?.display_label} size="sm" />

                {proposedChangesDetails?.created_by?.node?.display_label}

                <DateDisplay
                  date={proposedChangesDetails.description.updated_at}
                  className="ml-auto text-xs font-normal text-gray-600"
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
          <CardWithBorder.Title className="flex justify-between items-center">
            <div
              onClick={() => navigate(path)}
              className="text-base font-semibold leading-6 text-gray-900 cursor-pointer hover:underline"
            >
              Proposed change
            </div>

            <ProposedChangeEditTrigger proposedChangesDetails={proposedChangesDetails} />
          </CardWithBorder.Title>

          <PropertyList properties={proposedChangeProperties} />
        </CardWithBorder>
      </div>
    </div>
  );
};

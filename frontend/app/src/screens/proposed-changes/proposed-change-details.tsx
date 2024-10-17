import { Avatar } from "@/components/display/avatar";
import { DateDisplay } from "@/components/display/date-display";
import { MarkdownViewer } from "@/components/editor/markdown-viewer";
import { Property, PropertyList } from "@/components/table/property-list";
import { Badge } from "@/components/ui/badge";
import { CardWithBorder } from "@/components/ui/card";
import { Tooltip } from "@/components/ui/tooltip";
import { PcApproveButton } from "@/screens/proposed-changes/action-button/pc-approve-button";
import { PcCloseButton } from "@/screens/proposed-changes/action-button/pc-close-button";
import { PcMergeButton } from "@/screens/proposed-changes/action-button/pc-merge-button";
import { Conversations } from "@/screens/proposed-changes/conversations";
import { ProposedChangeEditTrigger } from "@/screens/proposed-changes/proposed-change-edit-trigger";
import { proposedChangedState } from "@/state/atoms/proposedChanges.atom";
import { classNames } from "@/utils/common";
import { constructPath } from "@/utils/fetch";
import { getProposedChangesStateBadgeType } from "@/utils/proposed-changes";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { HTMLAttributes } from "react";
import { useNavigate, useParams } from "react-router-dom";

export const ProposedChangeDetails = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => {
  const { proposedChangeId } = useParams();
  const [proposedChangesDetails] = useAtom(proposedChangedState);

  const navigate = useNavigate();

  const reviewers = proposedChangesDetails?.reviewers?.edges.map((edge: any) => edge.node) ?? [];
  const approvers = proposedChangesDetails?.approved_by?.edges.map((edge: any) => edge.node) ?? [];

  const path = constructPath("/proposed-changes");
  const state = proposedChangesDetails?.state?.value;

  const proposedChangeProperties: Property[] = [
    {
      name: "ID",
      value: proposedChangesDetails.id,
    },
    {
      name: "State",
      value: <Badge variant={getProposedChangesStateBadgeType(state)}>{state}</Badge>,
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
        <Tooltip enabled content={proposedChangesDetails?.created_by?.node?.display_label}>
          <Avatar
            size={"sm"}
            name={proposedChangesDetails?.created_by?.node?.display_label}
            className="mr-2 bg-custom-blue-green"
          />
        </Tooltip>
      ),
    },
    {
      name: "Approvers",
      value: approvers.map((approver: any, index: number) => (
        <Tooltip key={index} content={approver.display_label}>
          <Avatar size={"sm"} name={approver.display_label} className="mr-2" />
        </Tooltip>
      )),
    },
    {
      name: "Reviewers",
      value: reviewers.map((reviewer: any, index: number) => (
        <Tooltip key={index} content={reviewer.display_label}>
          <Avatar size={"sm"} name={reviewer.display_label} className="mr-2" />
        </Tooltip>
      )),
    },
    {
      name: "Updated",
      value: <DateDisplay date={proposedChangesDetails?._updated_at} />,
    },
    {
      name: "Actions",
      value: (
        <div className="flex flex-wrap gap-2">
          <PcApproveButton
            approvers={approvers}
            proposedChangeId={proposedChangeId!}
            state={state}
          />
          <PcMergeButton
            proposedChangeId={proposedChangeId!}
            state={state}
            sourceBranch={proposedChangesDetails?.source_branch?.value}
          />
          <PcCloseButton proposedChangeId={proposedChangeId!} state={state} />
        </div>
      ),
    },
  ];

  return (
    <div className={classNames("grid grid-cols-3 gap-2 p-2.5 items-start", className)} {...props}>
      <div className="col-start-1 col-end-3 space-y-4">
        {proposedChangesDetails?.description?.value && (
          <CardWithBorder contentClassName="p-4" data-testid="pc-description">
            <div className="flex items-center gap-2 mb-2">
              <Avatar name={proposedChangesDetails?.created_by?.node?.display_label} size="sm" />

              {proposedChangesDetails?.created_by?.node?.display_label}

              <DateDisplay
                date={proposedChangesDetails.description.updated_at}
                className="ml-auto text-xs font-normal text-gray-600"
              />
            </div>

            <MarkdownViewer markdownText={proposedChangesDetails.description.value} />
          </CardWithBorder>
        )}

        <Conversations />
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
  );
};

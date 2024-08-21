import { Avatar } from "@/components/display/avatar";
import { DateDisplay } from "@/components/display/date-display";
import { Tooltip } from "@/components/ui/tooltip";
import { proposedChangedState } from "@/state/atoms/proposedChanges.atom";
import { constructPath } from "@/utils/fetch";
import { getProposedChangesStateBadgeType } from "@/utils/proposed-changes";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import React from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CardWithBorder } from "@/components/ui/card";
import { Property, PropertyList } from "@/components/table/property-list";
import { Badge } from "@/components/ui/badge";
import { ProposedChangeEditTrigger } from "@/screens/proposed-changes/proposed-change-edit-trigger";
import { PcCloseButton } from "@/screens/proposed-changes/action-button/pc-close-button";
import { PcMergeButton } from "@/screens/proposed-changes/action-button/pc-merge-button";
import { PcApproveButton } from "@/screens/proposed-changes/action-button/pc-approve-button";

export const ProposedChangeDetails = () => {
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
      name: "Name",
      value: proposedChangesDetails?.name?.value,
    },
    {
      name: "Description",
      value: proposedChangesDetails?.description?.value,
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
          <PcApproveButton approvers={approvers} proposedChangeId={proposedChangeId!} />
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
    <CardWithBorder>
      <CardWithBorder.Title className="flex justify-between items-center">
        <div
          onClick={() => navigate(path)}
          className="text-base font-semibold leading-6 text-gray-900 cursor-pointer hover:underline">
          Proposed change
        </div>

        <ProposedChangeEditTrigger proposedChangesDetails={proposedChangesDetails} />
      </CardWithBorder.Title>

      <PropertyList properties={proposedChangeProperties} />
    </CardWithBorder>
  );
};

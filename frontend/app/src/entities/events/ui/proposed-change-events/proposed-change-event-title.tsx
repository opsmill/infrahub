import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { BranchRebasedEvent } from "@/shared/api/graphql/generated/graphql";
import { ReactNode } from "react";

export const PROPOSED_CHANGE_EVENTS_MAPPING: Record<string, (props: any) => ReactNode> = {
  "infrahub.proposed_change.review_revoked": (props) => {
    console.log("props: ", props);
    return <div className="text-gray-600">REVIEW REVOKED</div>;
  },
  "infrahub.branch.reviewed": (props: BranchRebasedEvent) => {
    console.log("props: ", props);
    return <div className="text-gray-600">REVIEWED</div>;
  },
};

export const ProposedChangeEventTitle = (props: any) => {
  const { event, account_id, branch } = props;

  return (
    <div className="flex items-center flex-wrap gap-2 text-sm">
      <NodeLabel id={account_id} kind="CoreAccount" branch={branch} />

      {PROPOSED_CHANGE_EVENTS_MAPPING[event] && PROPOSED_CHANGE_EVENTS_MAPPING[event](props)}
    </div>
  );
};

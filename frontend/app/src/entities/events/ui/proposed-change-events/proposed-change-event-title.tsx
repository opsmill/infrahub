import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { ReactNode } from "react";

export const PROPOSED_CHANGE_EVENTS_MAPPING: Record<string, (props: any) => ReactNode> = {
  "infrahub.proposed_change.merged": () => {
    return <div className="text-gray-600">merged the proposed change</div>;
  },
  "infrahub.proposed_change.review_requested": () => {
    return <div className="text-gray-600">requested a review</div>;
  },
  "infrahub.proposed_change.approved": () => {
    return <div className="text-gray-600">approved the proposed change</div>;
  },
  "infrahub.proposed_change.rejected": () => {
    return <div className="text-gray-600">rejected the proposed change</div>;
  },
  "infrahub.proposed_change.approval_revoked": () => {
    return <div className="text-gray-600">canceled its approval</div>;
  },
  "infrahub.proposed_change.rejection_revoked": () => {
    return <div className="text-gray-600">canceled its rejection</div>;
  },
};

export const ProposedChangeEventTitle = (props: any) => {
  const { event, account_id, branch } = props;

  return (
    <div className="flex items-center flex-wrap gap-1 text-sm">
      <NodeLabel id={account_id} kind="CoreAccount" branch={branch} />

      {PROPOSED_CHANGE_EVENTS_MAPPING[event] && PROPOSED_CHANGE_EVENTS_MAPPING[event](props)}
    </div>
  );
};

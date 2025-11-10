import type { ReactNode } from "react";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import {
  PROPOSED_CHANGE_APPROVALS_REVOKED,
  PROPOSED_CHANGE_THREAD,
} from "@/entities/proposed-changes/constants";

import { ProposedChangeThreadEvent } from "./proposed-change-thread-event";

export const PROPOSED_CHANGE_EVENTS_MAPPING: Record<string, () => ReactNode> = {
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
    return <div className="text-gray-600">canceled the approval</div>;
  },
  "infrahub.proposed_change.rejection_revoked": () => {
    return <div className="text-gray-600">canceled the rejection</div>;
  },
};

type Event = keyof typeof PROPOSED_CHANGE_EVENTS_MAPPING | typeof PROPOSED_CHANGE_THREAD;

interface ProposedChangeEventTitleProps {
  event: Event;
  account_id: string;
  branch: string;
  related_nodes?: Array<{ id: string }>;
}

export const ProposedChangeEventTitle = (props: ProposedChangeEventTitleProps) => {
  const { event, account_id, branch } = props;

  if (event === PROPOSED_CHANGE_APPROVALS_REVOKED) {
    return (
      <div className="text-gray-600">Changes occurred in the source branch, approval revoked</div>
    );
  }

  if (event === PROPOSED_CHANGE_THREAD && props.related_nodes?.[0]?.id) {
    return (
      <div className="flex flex-col gap-2">
        <div className="flex gap-1 text-sm">
          <NodeLabel id={account_id} kind="CoreAccount" branch={branch} />{" "}
          <span className="text-gray-600">created a thread</span>
        </div>

        <ProposedChangeThreadEvent id={props.related_nodes?.[0].id} />
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-1 text-sm">
      <NodeLabel id={account_id} kind="CoreAccount" branch={branch} />

      {PROPOSED_CHANGE_EVENTS_MAPPING[event] && PROPOSED_CHANGE_EVENTS_MAPPING[event]()}
    </div>
  );
};

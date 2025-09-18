import type { ReactNode } from "react";

import type {
  BranchCreatedEvent,
  BranchDeletedEvent,
  BranchMergedEvent,
  BranchRebasedEvent,
} from "@/shared/api/graphql/generated/graphql";
import { Link } from "@/shared/components/ui/link";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";

export const BRANCH_EVENTS_MAPPING: Record<string, (props: any) => ReactNode> = {
  "infrahub.branch.created": (props: BranchCreatedEvent) => (
    <div className="text-gray-600">
      created the branch{" "}
      <Link to={`/branches/${props.created_branch}`} className="text-black">
        {props.created_branch ?? "-"}
      </Link>
    </div>
  ),
  "infrahub.branch.rebased": (props: BranchRebasedEvent) => (
    <div className="text-gray-600">
      rebased the branch{" "}
      <Link to={`/branches/${props.rebased_branch}`} className="text-black">
        {props.rebased_branch ?? "-"}
      </Link>
    </div>
  ),
  "infrahub.branch.merged": (props: BranchMergedEvent) => (
    <div className="text-gray-600">
      merged the branch <span className="text-black">{props.source_branch ?? "-"}</span>
    </div>
  ),
  "infrahub.branch.deleted": (props: BranchDeletedEvent) => (
    <div className="text-gray-600">
      deleted the branch <span className="text-black">{props.deleted_branch ?? "-"}</span>
    </div>
  ),
};

export const BranchEventTitle = (props: any) => {
  const { event, account_id, branch } = props;

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <NodeLabel id={account_id} kind="CoreAccount" branch={branch} />

      {BRANCH_EVENTS_MAPPING[event] && BRANCH_EVENTS_MAPPING[event](props)}
    </div>
  );
};

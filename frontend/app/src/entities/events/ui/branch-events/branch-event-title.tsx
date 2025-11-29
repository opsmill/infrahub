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
    <div className="flex min-w-0 items-center gap-1 text-gray-600">
      <span className="whitespace-nowrap">created the branch</span>
      <Link to={`/branches/${props.created_branch}`} className="min-w-0 truncate text-black">
        {props.created_branch ?? "-"}
      </Link>
    </div>
  ),
  "infrahub.branch.rebased": (props: BranchRebasedEvent) => (
    <div className="flex min-w-0 items-center gap-1 text-gray-600">
      <span className="whitespace-nowrap">rebased the branch</span>
      <Link to={`/branches/${props.rebased_branch}`} className="min-w-0 truncate text-black">
        {props.rebased_branch ?? "-"}
      </Link>
    </div>
  ),
  "infrahub.branch.merged": (props: BranchMergedEvent) => (
    <div className="flex min-w-0 items-center gap-1 text-gray-600">
      <span className="whitespace-nowrap">merged the branch</span>
      <span className="min-w-0 truncate text-black">{props.source_branch ?? "-"}</span>
    </div>
  ),
  "infrahub.branch.deleted": (props: BranchDeletedEvent) => (
    <div className="flex min-w-0 items-center gap-1 text-gray-600">
      <span className="whitespace-nowrap">deleted the branch</span>
      <span className="min-w-0 truncate text-black">{props.deleted_branch ?? "-"}</span>
    </div>
  ),
};

export const BranchEventTitle = (props: any) => {
  const { event, account_id, branch } = props;

  return (
    <div className="flex w-full min-w-0 items-center gap-1 overflow-hidden text-sm">
      {account_id ? (
        <span className="max-w-[200px] shrink-0 truncate">
          <NodeLabel id={account_id} kind="CoreAccount" branch={branch} />
        </span>
      ) : (
        "-"
      )}

      {BRANCH_EVENTS_MAPPING[event] && BRANCH_EVENTS_MAPPING[event](props)}
    </div>
  );
};

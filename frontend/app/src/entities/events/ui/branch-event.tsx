import { EventNodeInterface } from "@/shared/api/graphql/generated/graphql";
import { ReactNode } from "react";

export const BRANCH_EVENTS_MAPPING: Record<string, (param: string) => ReactNode> = {
  "infrahub.branch.created": (branch) => (
    <div>
      Branch <span className="text-black font-semibold">{branch}</span> created
    </div>
  ),
  "infrahub.branch.rebased": (branch) => (
    <div>
      Branch <span className="text-black font-semibold">{branch}</span> rebased
    </div>
  ),
  "infrahub.branch.deleted": (branch) => (
    <div>
      Branch <span className="text-black font-semibold">{branch}</span> deleted
    </div>
  ),
};

export const BranchEvent = (props: EventNodeInterface) => {
  const { event, branch } = props;

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          <div className="text-gray-500">
            {branch && BRANCH_EVENTS_MAPPING[event] && BRANCH_EVENTS_MAPPING[event](branch)}
          </div>
        </div>
      </div>
    </>
  );
};

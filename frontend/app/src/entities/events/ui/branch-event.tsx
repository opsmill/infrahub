import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { EventNodeInterface } from "@/shared/api/graphql/generated/graphql";
import { ReactNode } from "react";

export const BRANCH_EVENTS_MAPPING: Record<string, (props: EventNodeInterface) => ReactNode> = {
  "infrahub.branch.created": (props) => (
    <div>
      created the branch <span className="text-black font-semibold">{props.branch}</span>{" "}
    </div>
  ),
  "infrahub.branch.rebased": (props) => (
    <div>
      rebased the branch <span className="text-black font-semibold">{props.branch}</span>{" "}
    </div>
  ),
  "infrahub.branch.deleted": (props) => (
    <div>
      deleted the branch <span className="text-black font-semibold">{props.branch}</span>{" "}
    </div>
  ),
};

export const BranchEvent = (props: EventNodeInterface) => {
  const { event, account_id } = props;

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          <div className="text-gray-500">
            <div className="font-semibold">
              <NodeLabel id={account_id} />
            </div>

            {BRANCH_EVENTS_MAPPING[event] && BRANCH_EVENTS_MAPPING[event](props)}
          </div>
        </div>
      </div>
    </>
  );
};

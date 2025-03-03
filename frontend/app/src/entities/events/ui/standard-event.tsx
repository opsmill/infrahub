import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { EventNodeInterface } from "@/shared/api/graphql/generated/graphql";
import { Link } from "@/shared/components/ui/link";
import { ReactElement } from "react";

export const STANDARD_EVENTS_MAPPING: Record<string, (props: EventNodeInterface) => ReactElement> =
  {
    "infrahub.schema.update": () => {
      return <div className="flex items-center gap-2">updated the schema</div>;
    },
    "infrahub.branch.create": (props) => {
      return (
        <div className="flex items-center gap-2">
          merged the branch
          <Link to={`/branches/${props.payload?.context?.branch?.name}`} className="text-black">
            {props.payload?.context?.branch?.name}
          </Link>
        </div>
      );
    },
    "infrahub.branch.merged": (props) => {
      return (
        <div className="flex items-center gap-2">
          merged the branch
          <Link to={`/branches/${props.payload?.context?.branch?.name}`} className="text-black">
            {props.payload?.context?.branch?.name}
          </Link>
        </div>
      );
    },
  };

export const StandardEvent = (props: EventNodeInterface) => {
  const { event, account_id } = props;

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          <div className="font-semibold">
            <NodeLabel id={account_id} />
          </div>

          <div className="text-gray-500">
            {STANDARD_EVENTS_MAPPING[event] && STANDARD_EVENTS_MAPPING[event](props)}

            {!STANDARD_EVENTS_MAPPING[event] && event}
          </div>
        </div>
      </div>
    </>
  );
};

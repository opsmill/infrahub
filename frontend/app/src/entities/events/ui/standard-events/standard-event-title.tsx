import { QSP } from "@/config/qsp";
import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { EventNodeInterface } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { Link } from "@/shared/components/ui/link";
import { ReactElement } from "react";

export const STANDARD_EVENTS_MAPPING: Record<string, (props: EventNodeInterface) => ReactElement> =
  {
    "infrahub.schema.update": () => {
      return <div className="flex flex-wrap items-center gap-2">updated the schema</div>;
    },
    "infrahub.repository.update_commit": (props) => {
      return (
        <div className="flex flex-wrap items-center gap-2">
          updated the commit
          <span className="text-black">{props.payload?.commit}</span>
          from repository
          <Link
            className="text-black"
            to={constructPath(`/objects/CoreRepository/${props.payload?.repository_id}`, [
              { name: QSP.BRANCH, value: props.payload?.context?.branch?.name },
            ])}
          >
            {props.payload?.repository_name}
          </Link>
        </div>
      );
    },
  };

export const StandardEventTitle = (props: EventNodeInterface) => {
  const { event, account_id, branch } = props;

  return (
    <div className="flex items-center flex-wrap gap-1 text-sm">
      <NodeLabel id={account_id} kind="CoreAccount" branch={branch} />

      <div className="text-gray-500">
        {STANDARD_EVENTS_MAPPING[event] && STANDARD_EVENTS_MAPPING[event](props)}

        {!STANDARD_EVENTS_MAPPING[event] && event}
      </div>
    </div>
  );
};

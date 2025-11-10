import type { ReactElement } from "react";

import { QSP } from "@/config/qsp";

import type { StandardEvent } from "@/shared/api/graphql/generated/graphql";
import { Link } from "@/shared/components/ui/link";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";

export const STANDARD_EVENTS_MAPPING: Record<string, (props: StandardEvent) => ReactElement> = {
  "infrahub.schema.update": () => {
    return <div className="flex flex-wrap items-center gap-1">updated the schema</div>;
  },
  "infrahub.repository.update_commit": (props) => {
    return (
      <div className="flex flex-wrap items-center gap-1">
        updated the commit
        <span className="text-black">{props.payload?.commit}</span>
        from repository
        <Link
          className="text-black"
          to={getObjectDetailsUrl("CoreRepository", props.payload?.repository_id, [
            { name: QSP.BRANCH, value: props.payload?.context?.branch?.name },
          ])}
        >
          {props.payload?.repository_name}
        </Link>
      </div>
    );
  },
};

export const StandardEventTitle = (props: StandardEvent) => {
  const { event, account_id, branch } = props;

  return (
    <div className="flex flex-wrap items-center gap-1 text-sm">
      <NodeLabel id={account_id} kind="CoreAccount" branch={branch} />

      <div className="text-gray-600">
        {STANDARD_EVENTS_MAPPING[event] && STANDARD_EVENTS_MAPPING[event](props)}

        {!STANDARD_EVENTS_MAPPING[event] && event}
      </div>
    </div>
  );
};

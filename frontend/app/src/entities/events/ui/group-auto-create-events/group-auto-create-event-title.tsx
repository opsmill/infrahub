import type React from "react";

import { classNames, warnUnexpectedType } from "@/shared/utils/common";

import type { GroupAutoCreateEvent } from "@/entities/events/types";
import { NodeLabel } from "@/entities/nodes/object/ui/node-label";

interface AutoCreateLayoutProps {
  accountId: string | null;
  triggeringUserName: string;
  branch: string | null;
  children: React.ReactNode;
}

const AutoCreateLayout = ({
  accountId,
  triggeringUserName,
  branch,
  children,
}: AutoCreateLayoutProps) => {
  return (
    <div className="flex w-full min-w-0 items-center gap-1 overflow-hidden text-sm">
      <span className="max-w-50 shrink-0 truncate">
        {accountId ? (
          <NodeLabel id={accountId} kind="CoreAccount" branch={branch} />
        ) : (
          triggeringUserName
        )}
      </span>

      <span className="flex min-w-0 items-center gap-1 whitespace-nowrap text-gray-600">
        {children}
      </span>
    </div>
  );
};

const Highlight = ({ children }: { children: React.ReactNode }) => {
  return <span className={classNames("max-w-50 truncate font-medium text-black")}>{children}</span>;
};

export const GroupAutoCreateEventTitle = (props: GroupAutoCreateEvent) => {
  const layoutProps = {
    accountId: props.account_id,
    triggeringUserName: props.triggering_user_name,
    branch: props.branch,
  };

  switch (props.__typename) {
    case "GroupAutoCreatedEventType": {
      return (
        <AutoCreateLayout {...layoutProps}>
          auto-created group <Highlight>{props.group_name}</Highlight> from {props.idp}
        </AutoCreateLayout>
      );
    }
    case "GroupAutoCreateRejectedEventType": {
      return (
        <AutoCreateLayout {...layoutProps}>
          had auto-create claim <Highlight>{props.rejected_claim_value}</Highlight> rejected from{" "}
          {props.idp}
        </AutoCreateLayout>
      );
    }
    case "GroupAutoCreateCappedEventType": {
      return (
        <AutoCreateLayout {...layoutProps}>
          reached the auto-create cap of <Highlight>{props.cap_value}</Highlight>, dropping{" "}
          {props.dropped_count} claim{props.dropped_count === 1 ? "" : "s"} from {props.idp}
        </AutoCreateLayout>
      );
    }
    default: {
      warnUnexpectedType(props);
      return <span className="text-gray-600 text-sm">{(props as GroupAutoCreateEvent).event}</span>;
    }
  }
};

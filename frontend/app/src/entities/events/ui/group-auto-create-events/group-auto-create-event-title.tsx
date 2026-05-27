import type React from "react";

import { classNames, warnUnexpectedType } from "@/shared/utils/common";

import type { GroupAutoCreateEvent } from "@/entities/events/types";

interface AutoCreateLayoutProps {
  idp: string;
  children: React.ReactNode;
}

const AutoCreateLayout = ({ idp, children }: AutoCreateLayoutProps) => {
  return (
    <div className="flex w-full min-w-0 items-center gap-1 overflow-hidden text-sm">
      <span className="max-w-50 shrink-0 truncate font-medium text-black">{idp}</span>

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
  switch (props.__typename) {
    case "GroupAutoCreatedEventType": {
      return (
        <AutoCreateLayout idp={props.idp}>
          auto-created group <Highlight>{props.group_name}</Highlight>
        </AutoCreateLayout>
      );
    }
    case "GroupAutoCreateRejectedEventType": {
      return (
        <AutoCreateLayout idp={props.idp}>
          claim <Highlight>{props.rejected_claim_value}</Highlight> rejected (invalid group name)
        </AutoCreateLayout>
      );
    }
    case "GroupAutoCreateCappedEventType": {
      return (
        <AutoCreateLayout idp={props.idp}>
          auto-create cap of <Highlight>{props.cap_value}</Highlight> reached, {props.dropped_count}{" "}
          claim{props.dropped_count === 1 ? "" : "s"} dropped
        </AutoCreateLayout>
      );
    }
    default: {
      warnUnexpectedType(props);
      return <span className="text-gray-600 text-sm">{(props as GroupAutoCreateEvent).event}</span>;
    }
  }
};

import { warnUnexpectedType } from "@/shared/utils/common";

import type { EventType } from "@/entities/events/domain/model/event";
import { AccountLoggedInEventTitle } from "@/entities/events/ui/account-events/account-logged-in-event-title";
import { AccountLoggedOutEventTitle } from "@/entities/events/ui/account-events/account-logged-out-event-title";
import { ArtifactEventTitle } from "@/entities/events/ui/artifact-events/artifact-event-title";
import { BranchEventTitle } from "@/entities/events/ui/branch-events/branch-event-title";
import { GroupAutoCreateEventTitle } from "@/entities/events/ui/group-auto-create-events/group-auto-create-event-title";
import { GroupEventTitle } from "@/entities/events/ui/group-events/group-event-title";
import { NodeEventTitle } from "@/entities/events/ui/node-events/node-event-title";
import { ProposedChangeEventTitle } from "@/entities/events/ui/proposed-change-events/proposed-change-event-title";
import { StandardEventTitle } from "@/entities/events/ui/standard-events/standard-event-title";
import { PROPOSED_CHANGE_EVENTS } from "@/entities/proposed-changes/domain/model/proposed-change-events";

const EventName = ({ name }: { name: string }) => {
  return <span className="flex items-center text-foreground-muted text-sm">{name}</span>;
};

interface EventTitleProps {
  event: EventType;
}

export const EventTitle = ({ event }: EventTitleProps) => {
  if ("attributes" in event) {
    return <NodeEventTitle {...event} />;
  }

  // Branch events come first because the proposed-change event names include branch merges and deletions.
  if (
    event.__typename === "BranchCreatedEvent" ||
    event.__typename === "BranchDeletedEvent" ||
    event.__typename === "BranchMergedEvent" ||
    event.__typename === "BranchRebasedEvent"
  ) {
    return <BranchEventTitle {...event} />;
  }

  if (PROPOSED_CHANGE_EVENTS.includes(event.event)) {
    return <ProposedChangeEventTitle {...event} />;
  }

  switch (event.__typename) {
    case "StandardEvent": {
      return <StandardEventTitle {...event} />;
    }
    case "GroupEvent": {
      return <GroupEventTitle {...event} />;
    }
    case "GroupAutoCreatedEventType":
    case "GroupAutoCreateRejectedEventType":
    case "GroupAutoCreateCappedEventType": {
      return <GroupAutoCreateEventTitle {...event} />;
    }
    case "ArtifactEvent": {
      return <ArtifactEventTitle {...event} />;
    }
    case "AccountLoggedInEventType": {
      return <AccountLoggedInEventTitle {...event} />;
    }
    case "AccountLoggedOutEventType": {
      return <AccountLoggedOutEventTitle {...event} />;
    }
    case "ProposedChangeApprovalsRevokedEvent":
    case "ProposedChangeMergedEvent":
    case "ProposedChangeReviewEvent":
    case "ProposedChangeReviewRequestedEvent":
    case "ProposedChangeReviewRevokedEvent":
    case "ProposedChangeThreadEvent": {
      return <EventName name={event.event} />;
    }
    default: {
      warnUnexpectedType(event);
      return <EventName name={(event as EventType).event} />;
    }
  }
};

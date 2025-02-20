import { EventNodeInterface, NodeMutatedEvent } from "@/shared/api/graphql/generated/graphql";
import { DateDisplay } from "@/shared/components/display/date-display";

import { NodeLabel } from "@/entities/nodes/object/ui/display-label";
import { PropertyRow } from "@/entities/schema/ui/styled";
import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { TimelineBorder } from "@/shared/components/ui/timeline-border";
import {
  BRANCH_CREATED_EVENT,
  BRANCH_DELETED_EVENT,
  BRANCH_EVENTS,
  BRANCH_REBASEDED_EVENT,
  NODE_MUTATED_EVENT,
  STANDARD_EVENTS,
} from "../utils/constants";
import { BranchEvent } from "./branch-event";
import { EventAttributes, NodeEvent } from "./node-event";
import { StandardEvent } from "./standard-event";

export type BranchEventType = EventNodeInterface & {
  __typename:
    | typeof BRANCH_DELETED_EVENT
    | typeof BRANCH_CREATED_EVENT
    | typeof BRANCH_REBASEDED_EVENT;
};

export type NodeEventType = NodeMutatedEvent & {
  __typename: typeof NODE_MUTATED_EVENT;
};

export type EventType = BranchEventType | NodeEventType;

export const EventDetails = ({ id, event, occurred_at, account_id, ...props }: EventType) => {
  return (
    <div className="divide-y">
      <PropertyRow
        title="ID"
        value={
          <div className="flex items-center gap-2">
            {id} <CopyToClipboard text={id} />
          </div>
        }
      />
      <PropertyRow title="Event" value={event} />
      <PropertyRow title="Occured at" value={<DateDisplay date={occurred_at} />} />
      {account_id && <PropertyRow title="Account" value={<NodeLabel id={account_id} />} />}
      {"attributes" in props && (
        <PropertyRow title="Changes" value={<EventAttributes attributes={props.attributes} />} />
      )}
    </div>
  );
};

export const Event = ({ __typename, ...props }: EventType) => {
  return (
    <div className="flex gap-2">
      <TimelineBorder />

      <div className="flex flex-grow gap-3 p-2 rounded-md shadow-sm border bg-white">
        <div className="flex flex-col gap-2 grow">
          {"attributes" in props && <NodeEvent {...props} />}

          {"attributes" in props && <EventAttributes attributes={props.attributes} />}

          {BRANCH_EVENTS.includes(__typename) && <BranchEvent {...props} />}

          {STANDARD_EVENTS.includes(__typename) && <StandardEvent {...props} />}

          <div className="flex justify-between">
            <div className="text-xs font-medium text-gray-500 dark:text-neutral-400">
              <DateDisplay date={props.occurred_at} />
            </div>

            <Popover>
              <PopoverTrigger>
                <div className="flex flex-grow justify-end">
                  <p className="text-sm underline text-gray-600 dark:text-neutral-400 mb-1">
                    View more.
                  </p>
                </div>
              </PopoverTrigger>
              <PopoverContent className="w-full">
                <EventDetails {...props} />
              </PopoverContent>
            </Popover>
          </div>
        </div>
      </div>
    </div>
  );
};

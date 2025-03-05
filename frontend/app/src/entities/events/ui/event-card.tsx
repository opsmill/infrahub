import { DateDisplay } from "@/shared/components/display/date-display";

import { ACCOUNT_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { EventType } from "@/entities/events/types";
import { EventAttributes } from "@/entities/events/ui/node-events/event-attributes";
import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { PropertyRow } from "@/entities/schema/ui/styled";
import { constructPath } from "@/shared/api/rest/fetch";
import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import { Link } from "@/shared/components/ui/link";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { TimelineBorder } from "@/shared/components/ui/timeline-border";
import { BRANCH_EVENTS, STANDARD_EVENTS } from "../constants";
import { BranchEvent } from "./branch-events/branch-event";
import { NodeEventTitle } from "./node-events/node-event-title";
import { StandardEvent } from "./standard-event";

export const EventDetails = ({
  id,
  event,
  branch,
  occurred_at,
  account_id,
  primary_node,
  related_nodes,
  ancestors,
  members,
  ...props
}: EventType) => {
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
      <PropertyRow title="Branch" value={branch} />
      <PropertyRow title="Occured at" value={<DateDisplay date={occurred_at} />} />
      {account_id && (
        <PropertyRow
          title="Account"
          value={
            <Link
              to={constructPath(`/${ACCOUNT_OBJECT}/${account_id}`, [
                { name: QSP.BRANCH, value: props.branch },
              ])}
            >
              <NodeLabel id={account_id} />
            </Link>
          }
        />
      )}
      {primary_node?.id && (
        <PropertyRow
          title="Primary Node"
          value={
            <Link
              to={constructPath(`/${primary_node.kind}/${primary_node.id}`, [
                { name: QSP.BRANCH, value: props.branch },
              ])}
            >
              <NodeLabel id={primary_node.id} />
            </Link>
          }
        />
      )}
      {!!related_nodes?.length && (
        <PropertyRow
          title="Related Nodes"
          value={
            <div className="flex flex-col items-end gap-1">
              {related_nodes.map((node) => {
                return (
                  <Link
                    key={node.id}
                    to={constructPath(`/${node.kind}/${node.id}`, [
                      { name: QSP.BRANCH, value: props.branch },
                    ])}
                  >
                    <NodeLabel id={node?.id} />
                  </Link>
                );
              })}
            </div>
          }
        />
      )}
      {!!ancestors?.length && (
        <PropertyRow
          title="Related Nodes"
          value={
            <div className="flex flex-col items-end gap-1">
              {ancestors.map((node) => {
                return (
                  <Link
                    key={node.id}
                    to={constructPath(`/${node.kind}/${node.id}`, [
                      { name: QSP.BRANCH, value: props.branch },
                    ])}
                  >
                    <NodeLabel id={node?.id} />
                  </Link>
                );
              })}
            </div>
          }
        />
      )}
      {!!members?.length && (
        <PropertyRow
          title="Related Nodes"
          value={
            <div className="flex flex-col items-end gap-1">
              {members.map((node) => {
                return (
                  <Link
                    key={node.id}
                    to={constructPath(`/${node.kind}/${node.id}`, [
                      { name: QSP.BRANCH, value: props.branch },
                    ])}
                  >
                    <NodeLabel id={node?.id} />
                  </Link>
                );
              })}
            </div>
          }
        />
      )}
      {"attributes" in props && (
        <PropertyRow title="Changes" value={<EventAttributes attributes={props.attributes} />} />
      )}
    </div>
  );
};

export const EventCard = ({ __typename, ...props }: EventType) => {
  return (
    <div className="flex gap-2">
      <TimelineBorder />

      <div className="flex flex-grow gap-3 p-2 rounded-md shadow-sm border bg-white">
        <div className="flex flex-col gap-2 grow">
          {"attributes" in props && <NodeEventTitle {...props} />}

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

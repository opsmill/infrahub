import { DateDisplay } from "@/shared/components/display/date-display";

import { ACCOUNT_OBJECT } from "@/config/constants";
import { EventType } from "@/entities/events/types";
import { EventDetailsPopover } from "@/entities/events/ui/event-details-popover";

import { QSP } from "@/config/qsp";
import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { getObjectDetailsUrl2 } from "@/entities/nodes/utils";
import { PropertyRow } from "@/entities/schema/ui/styled";
import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import { Link } from "@/shared/components/ui/link";
import { TimelineBorder } from "@/shared/components/ui/timeline-border";
import { Icon } from "@iconify-icon/react";
import { BRANCH_EVENTS, GROUP_EVENTS, STANDARD_EVENTS } from "../constants";
import { BranchEventTitle } from "./branch-events/branch-event-title";
import { GroupEventTitle } from "./group-events/group-event-title";
import { EventAttributes } from "./node-events/event-attributes";
import { NodeEventTitle } from "./node-events/node-event-title";
import { StandardEventTitle } from "./standard-events/standard-event-title";

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
              to={getObjectDetailsUrl2(ACCOUNT_OBJECT, account_id, [
                { name: QSP.BRANCH, value: branch },
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
              to={getObjectDetailsUrl2(primary_node.kind, primary_node.id, [
                { name: QSP.BRANCH, value: branch },
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
                    to={getObjectDetailsUrl2(node.kind, node.id, [
                      { name: QSP.BRANCH, value: branch },
                    ])}
                  >
                    <NodeLabel id={node.id} />
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
                    to={getObjectDetailsUrl2(node.kind, node.id, [
                      { name: QSP.BRANCH, value: branch },
                    ])}
                  >
                    <NodeLabel id={node.id} />
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
                    to={getObjectDetailsUrl2(node.kind, node.id, [
                      { name: QSP.BRANCH, value: branch },
                    ])}
                  >
                    <NodeLabel id={node.id} />
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

export const EventCard = (props: EventType) => {
  return (
    <div className="flex gap-2">
      <TimelineBorder />

      <div className="flex flex-grow gap-3 p-2 rounded-md shadow-sm border bg-white">
        <div className="flex flex-col gap-2 grow">
          {"attributes" in props && <NodeEventTitle {...props} />}

          {"attributes" in props && <EventAttributes attributes={props.attributes} />}

          {BRANCH_EVENTS.includes(props.__typename) && <BranchEventTitle {...props} />}

          {STANDARD_EVENTS.includes(props.__typename) && <StandardEventTitle {...props} />}

          {GROUP_EVENTS.includes(props.__typename) && <GroupEventTitle {...props} />}

          <div className="flex justify-between text-gray-500">
            <DateDisplay date={props.occurred_at} />

            <div className="flex items-center gap-4">
              {props.branch && (
                <div className="text-xs font-medium text-gray-500 flex items-center gap-1 whitespace-nowrap overflow-hidden text-ellipsis">
                  <Icon icon={"mdi:source-branch"} />

                  {props.branch}
                </div>
              )}

              <EventDetailsPopover {...props} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

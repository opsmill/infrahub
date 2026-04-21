import type {
  AccountLoggedInEventType,
  AccountLoggedOutEventType,
} from "@/shared/api/graphql/generated/types";
import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import { DateDisplay } from "@/shared/components/display/date-display";
import { Link } from "@/shared/components/ui/link";
import { ACCOUNT_OBJECT } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";

import type { EventType } from "@/entities/events/types";
import { EventAttributes } from "@/entities/events/ui/node-events/event-attributes";
import { EventRelationships } from "@/entities/events/ui/node-events/event-relationships";
import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { PropertyRow } from "@/entities/schema/ui/styled";

const AccountLoggedInEventDetails = ({ event }: { event: AccountLoggedInEventType }) => {
  return (
    <>
      <PropertyRow title="Account Name" value={event.account_name} />
      <PropertyRow title="Account Type" value={event.account_type} />
      <PropertyRow title="Auth Method" value={event.auth_method} />
      <PropertyRow title="Session ID" value={event.session_id} />
      <PropertyRow title="Event Timestamp" value={<DateDisplay date={event.timestamp} />} />
      <PropertyRow title="Client IP" value={event.client_ip} />
      <PropertyRow title="User Agent" value={event.user_agent} />
      <PropertyRow title="Identity Source" value={event.identity_source} />
      <PropertyRow title="Groups" value={event.groups?.join(", ")} />
      <PropertyRow title="Roles" value={event.roles?.join(", ")} />
    </>
  );
};

const AccountLoggedOutEventDetails = ({ event }: { event: AccountLoggedOutEventType }) => {
  return (
    <>
      <PropertyRow title="Account Name" value={event.account_name} />
      <PropertyRow title="Logout Type" value={event.logout_type} />
      <PropertyRow title="Session ID" value={event.session_id} />
      <PropertyRow title="Event Timestamp" value={<DateDisplay date={event.timestamp} />} />
      <PropertyRow title="Client IP" value={event.client_ip} />
      <PropertyRow title="User Agent" value={event.user_agent} />
    </>
  );
};

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
  const displayedBranch =
    branch ??
    ("deleted_branch" in props ? props.deleted_branch : undefined) ??
    ("created_branch" in props ? props.created_branch : undefined) ??
    ("rebased_branch" in props ? props.rebased_branch : undefined) ??
    ("source_branch" in props ? props.source_branch : undefined);

  return (
    <div className="divide-y divide-gray-200">
      <PropertyRow
        title="ID"
        value={
          <div className="flex items-center gap-2">
            {id} <CopyToClipboard text={id} />
          </div>
        }
      />

      <PropertyRow title="Event" value={event} />

      <PropertyRow title="Branch" value={displayedBranch} />

      <PropertyRow title="Occured at" value={<DateDisplay date={occurred_at} />} />

      {account_id && (
        <PropertyRow
          title="Account"
          value={
            <Link
              to={getObjectDetailsUrl(ACCOUNT_OBJECT, account_id, [
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
              to={getObjectDetailsUrl(primary_node.kind, primary_node.id, [
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
                    to={getObjectDetailsUrl(node.kind, node.id, [
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

      {"ancestors" in props && !!props.ancestors?.length && (
        <PropertyRow
          title="Ancestors"
          value={
            <div className="flex flex-col items-end gap-1">
              {props.ancestors.map((node) => {
                return (
                  <Link
                    key={node.id}
                    to={getObjectDetailsUrl(node.kind, node.id, [
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

      {"members" in props && !!props.members?.length && (
        <PropertyRow
          title="Members"
          value={
            <div className="flex flex-col items-end gap-1">
              {props.members.map((node) => {
                return (
                  <Link
                    key={node.id}
                    to={getObjectDetailsUrl(node.kind, node.id, [
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

      {"attributes" in props && !!props.attributes.length && (
        <PropertyRow title="Attributes" value={<EventAttributes attributes={props.attributes} />} />
      )}

      {"relationships" in props && !!props.relationships.length && (
        <PropertyRow
          title="Relationships"
          value={<EventRelationships relationships={props.relationships} />}
        />
      )}

      {props.__typename === "AccountLoggedInEventType" && (
        <AccountLoggedInEventDetails event={props} />
      )}

      {props.__typename === "AccountLoggedOutEventType" && (
        <AccountLoggedOutEventDetails event={props} />
      )}
    </div>
  );
};

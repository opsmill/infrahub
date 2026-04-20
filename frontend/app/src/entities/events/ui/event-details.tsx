import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import { DateDisplay } from "@/shared/components/display/date-display";
import { Link } from "@/shared/components/ui/link";
import { ACCOUNT_OBJECT } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { PropertyRow } from "@/entities/schema/ui/styled";

import type { EventType } from "../types";
import { EventAttributes } from "./node-events/event-attributes";
import { EventRelationships } from "./node-events/event-relationships";

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

      {!!ancestors?.length && (
        <PropertyRow
          title="Ancestors"
          value={
            <div className="flex flex-col items-end gap-1">
              {ancestors.map((node) => {
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

      {!!members?.length && (
        <PropertyRow
          title="Members"
          value={
            <div className="flex flex-col items-end gap-1">
              {members.map((node) => {
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
    </div>
  );
};

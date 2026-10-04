import { Button, Tooltip } from "@infrahub/ui";
import type React from "react";
import { Focusable } from "react-aria-components";
import { Link } from "react-router";

import { Col } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

import type {
  TreeMapChild,
  TreeMapFreeBlock,
  TreeMapRect,
  TreeMapTile,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { Permission } from "@/entities/permission/domain/model/permission";

const TOOLTIP_MEMBER_LIMIT = 20;

const TILE_BASE_CLASS = "relative block size-full overflow-hidden rounded-sm border text-xs";
const TILE_FOCUS_CLASS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring-halo";
const AGGREGATE_TILE_CLASS = "border-border bg-content-strong text-foreground-muted";

export const TREE_MAP_TILE_CLASSES = {
  allocated: "border-border bg-accent-surface text-foreground",
  free: "border-border-strong border-dashed bg-content text-foreground-muted",
  aggregate: AGGREGATE_TILE_CLASS,
} as const;

export interface IpPrefixTreeMapTileProps {
  rect: TreeMapRect;
  parent: { id: string; kind: string; cidr: string };
  permission: Permission;
  onCreateFromFreeBlock: (block: TreeMapFreeBlock) => void;
}

function formatUtilization(utilization: number | null): string {
  return utilization === null ? "utilization unknown" : `${Math.round(utilization)}% utilized`;
}

function formatMemberCount(child: TreeMapChild): string {
  const noun = child.memberType === "address" ? "IP address" : "child prefix";
  return `${child.memberCount} ${child.memberCount === 1 ? noun : `${noun}es`}`;
}

function formatMemberList(cidrs: string[]): string {
  const shown = cidrs.slice(0, TOOLTIP_MEMBER_LIMIT).join(", ");
  const hidden = cidrs.length - TOOLTIP_MEMBER_LIMIT;
  return hidden > 0 ? `${shown} and ${hidden} more` : shown;
}

function TileLabel({ children }: { children: React.ReactNode }) {
  return <span className="relative @min-[5rem]:block hidden truncate px-1 py-0.5">{children}</span>;
}

function AllocatedTooltip({ child }: { child: TreeMapChild }) {
  return (
    <Col className="gap-0.5">
      <span className="font-medium">{child.cidr}</span>
      {child.description && <span>{child.description}</span>}
      <span>Member type: {child.memberType}</span>
      <span>{formatUtilization(child.utilization)}</span>
      <span>{formatMemberCount(child)}</span>
    </Col>
  );
}

function AllocatedTile({ tile, child }: { tile: TreeMapTile; child: TreeMapChild }) {
  return (
    <Tooltip message={<AllocatedTooltip child={child} />}>
      <Focusable>
        <Link
          to={getObjectDetailsUrl(child.kind, child.id, undefined, "tree-map")}
          aria-label={`${child.cidr}, ${formatUtilization(child.utilization)}`}
          className={classNames(TILE_BASE_CLASS, TILE_FOCUS_CLASS, TREE_MAP_TILE_CLASSES.allocated)}
        >
          {child.utilization !== null && (
            <div
              data-testid="ip-prefix-tree-map-tile-fill"
              className="absolute inset-y-0 left-0 bg-accent-fill"
              style={{ width: `${child.utilization}%` }}
            />
          )}
          <TileLabel>{tile.label}</TileLabel>
        </Link>
      </Focusable>
    </Tooltip>
  );
}

function FreeTile({
  tile,
  block,
  permission,
  onCreateFromFreeBlock,
}: { tile: TreeMapTile; block: TreeMapFreeBlock } & Pick<
  IpPrefixTreeMapTileProps,
  "permission" | "onCreateFromFreeBlock"
>) {
  const isCreationAllowed = permission.create.isAllowed;

  return (
    <Tooltip message={isCreationAllowed ? block.cidr : permission.create.message}>
      <Button
        variant="ghost"
        aria-label={`${block.cidr} available`}
        isDisabledAndFocusable={!isCreationAllowed}
        onPress={() => onCreateFromFreeBlock(block)}
        className={classNames(
          TILE_BASE_CLASS,
          "items-start justify-start p-0 font-normal shadow-none",
          TREE_MAP_TILE_CLASSES.free
        )}
      >
        <TileLabel>{tile.label}</TileLabel>
      </Button>
    </Tooltip>
  );
}

function ParentChildrenLink({
  tile,
  parent,
  name,
  message,
}: {
  tile: TreeMapTile;
  parent: IpPrefixTreeMapTileProps["parent"];
  name: string;
  message: React.ReactNode;
}) {
  return (
    <Tooltip message={message}>
      <Focusable>
        <Link
          to={getObjectDetailsUrl(parent.kind, parent.id, undefined, "children")}
          aria-label={name}
          className={classNames(TILE_BASE_CLASS, TILE_FOCUS_CLASS, AGGREGATE_TILE_CLASS)}
        >
          <TileLabel>{tile.label}</TileLabel>
        </Link>
      </Focusable>
    </Tooltip>
  );
}

function AggregateFreeTile({ tile, members }: { tile: TreeMapTile; members: TreeMapFreeBlock[] }) {
  return (
    <Tooltip message={formatMemberList(members.map((member) => member.cidr))} nonInteractiveTrigger>
      <div
        role="img"
        aria-label={tile.label}
        className={classNames(TILE_BASE_CLASS, AGGREGATE_TILE_CLASS, "border-dashed")}
      >
        <TileLabel>{tile.label}</TileLabel>
      </div>
    </Tooltip>
  );
}

function TileContent({
  rect,
  parent,
  permission,
  onCreateFromFreeBlock,
}: IpPrefixTreeMapTileProps) {
  const { tile } = rect;

  switch (tile.kind) {
    case "allocated":
      return <AllocatedTile tile={tile} child={tile.child} />;
    case "free":
      return (
        <FreeTile
          tile={tile}
          block={tile.block}
          permission={permission}
          onCreateFromFreeBlock={onCreateFromFreeBlock}
        />
      );
    case "aggregate-allocated":
      return (
        <ParentChildrenLink
          tile={tile}
          parent={parent}
          name={tile.label}
          message={formatMemberList(tile.members.map((member) => member.cidr))}
        />
      );
    case "aggregate-free":
      return <AggregateFreeTile tile={tile} members={tile.members} />;
    case "remainder":
      return (
        <ParentChildrenLink
          tile={tile}
          parent={parent}
          name={`${tile.label} not shown`}
          message={`${tile.label} of ${parent.cidr} are not shown; open the Children tab to see them all`}
        />
      );
  }
}

export function IpPrefixTreeMapTile(props: IpPrefixTreeMapTileProps) {
  const { rect } = props;

  return (
    <div
      data-testid="ip-prefix-tree-map-tile"
      data-tile-kind={rect.tile.kind}
      className="@container absolute p-px"
      style={{
        left: `${rect.x}%`,
        top: `${rect.y}%`,
        width: `${rect.width}%`,
        height: `${rect.height}%`,
      }}
    >
      <TileContent {...props} />
    </div>
  );
}

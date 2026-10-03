import type React from "react";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { classNames } from "@/shared/utils/common";

import { TREE_MAP_ASPECT_RATIO } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";
import { buildTreeMapTiles } from "@/entities/ipam/ip-prefixes/domain/rules/build-tree-map-tiles";
import type { TreeMapParent } from "@/entities/ipam/ip-prefixes/domain/rules/get-tree-map-parent";
import { layoutTreeMap } from "@/entities/ipam/ip-prefixes/domain/rules/layout-tree-map";
import {
  IpPrefixTreeMapTile,
  TREE_MAP_FILL_BACKGROUND,
  TREE_MAP_TILE_CLASSES,
} from "@/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-tile";
import { useGetIpPrefixTreeMap } from "@/entities/ipam/ip-prefixes/ui/queries/get-ip-prefix-tree-map.query";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface IpPrefixTreeMapProps {
  parent: TreeMapParent;
  parentSchema: ModelSchema;
  permission: Permission;
}

// Creating a prefix from a free tile is wired by the create sheet, which lands separately.
const noopCreateFromFreeBlock = () => {};

function LegendSwatch({
  className,
  children,
  label,
}: {
  className: string;
  children?: React.ReactNode;
  label: string;
}) {
  return (
    <Row className="gap-1.5">
      <span className={classNames("relative size-3 overflow-hidden rounded-sm border", className)}>
        {children}
      </span>
      {label}
    </Row>
  );
}

function IpPrefixTreeMapLegend() {
  return (
    <Row className="flex-wrap gap-4 text-foreground-muted text-xs">
      <LegendSwatch className={TREE_MAP_TILE_CLASSES.allocated} label="Allocated">
        <span
          className="absolute inset-y-0 left-0 w-1/2"
          style={{ background: TREE_MAP_FILL_BACKGROUND }}
        />
      </LegendSwatch>
      <LegendSwatch className={TREE_MAP_TILE_CLASSES.free} label="Free" />
      <LegendSwatch
        className={TREE_MAP_TILE_CLASSES.aggregate}
        label="Smaller than 1/4096 of the prefix"
      />
    </Row>
  );
}

export function IpPrefixTreeMap({ parent, permission }: IpPrefixTreeMapProps) {
  const { isPending, error, data } = useGetIpPrefixTreeMap({ parentId: parent.id });

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const tiles = buildTreeMapTiles({
    parent,
    children: data.children,
    freeBlocks: data.freeBlocks,
    totalChildCount: data.totalChildCount,
  });
  const rects = layoutTreeMap(tiles, TREE_MAP_ASPECT_RATIO);

  return (
    <Col className="gap-3 p-2.5">
      <div
        role="group"
        aria-label={`Tree map of ${parent.cidr}`}
        data-testid="ip-prefix-tree-map"
        className="relative w-full"
        style={{ aspectRatio: `${TREE_MAP_ASPECT_RATIO} / 1` }}
      >
        {rects.map((rect) => (
          <IpPrefixTreeMapTile
            key={rect.tile.key}
            rect={rect}
            parent={parent}
            permission={permission}
            onCreateFromFreeBlock={noopCreateFromFreeBlock}
          />
        ))}
      </div>

      <IpPrefixTreeMapLegend />
    </Col>
  );
}

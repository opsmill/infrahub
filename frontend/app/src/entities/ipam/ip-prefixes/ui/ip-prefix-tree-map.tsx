import React from "react";

import { queryClient } from "@/shared/api/rest/client";
import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { classNames } from "@/shared/utils/common";
import { formatNumberDisplay } from "@/shared/utils/number";

import {
  TREE_MAP_ASPECT_RATIO,
  type TreeMapFreeBlock,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";
import { buildTreeMapTiles } from "@/entities/ipam/ip-prefixes/domain/rules/build-tree-map-tiles";
import { layoutTreeMap } from "@/entities/ipam/ip-prefixes/domain/rules/layout-tree-map";
import { IpPrefixCreateSheet } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-create-sheet";
import { IpPrefixTreeMapEmptyState } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-empty-state";
import {
  IpPrefixTreeMapTile,
  TREE_MAP_FILL_CLASSES,
  TREE_MAP_TILE_CLASSES,
} from "@/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-tile";
import { useGetIpPrefixTreeMap } from "@/entities/ipam/ip-prefixes/ui/queries/get-ip-prefix-tree-map.query";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface IpPrefixTreeMapProps {
  parentId: string;
  parentSchema: ModelSchema;
  permission: Permission;
}

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

function IpPrefixTreeMapLegend({ isCapped }: { isCapped: boolean }) {
  return (
    <Row className="flex-wrap gap-4 text-foreground-muted text-xs">
      <LegendSwatch className={TREE_MAP_TILE_CLASSES.allocated} label="Allocated">
        <span
          className={classNames("absolute inset-y-0 left-0 w-1/2", TREE_MAP_FILL_CLASSES.allocated)}
        />
      </LegendSwatch>
      <LegendSwatch className={TREE_MAP_TILE_CLASSES.pool} label="Pool">
        <span
          className={classNames("absolute inset-y-0 left-0 w-1/2", TREE_MAP_FILL_CLASSES.pool)}
        />
      </LegendSwatch>
      <LegendSwatch className={TREE_MAP_TILE_CLASSES.free} label="Free" />
      <LegendSwatch
        className={TREE_MAP_TILE_CLASSES.aggregate}
        label="Smaller than 1/4096 of the prefix"
      />
      {isCapped && <LegendSwatch className={TREE_MAP_TILE_CLASSES.notLoaded} label="Not loaded" />}
    </Row>
  );
}

export function IpPrefixTreeMap({ parentId, parentSchema, permission }: IpPrefixTreeMapProps) {
  const { isPending, error, data } = useGetIpPrefixTreeMap({ parentId });
  const [selectedFreeBlock, setSelectedFreeBlock] = React.useState<TreeMapFreeBlock | null>(null);

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const { parent } = data;

  // An address prefix can still hold child prefixes, so only the data decides between map and empty state.
  if (parent.memberType === "address" && data.children.length === 0) {
    return <IpPrefixTreeMapEmptyState utilization={parent.utilization} />;
  }

  const tiles = buildTreeMapTiles({
    parent,
    children: data.children,
    freeBlocks: data.freeBlocks,
    totalChildCount: data.totalChildCount,
  });
  const rects = layoutTreeMap(tiles, parent.size);

  return (
    <Col className="gap-3 p-2.5">
      {data.isCapped && (
        <p role="status" className="text-foreground-muted text-xs">
          Showing the first {formatNumberDisplay(data.children.length)} of{" "}
          {formatNumberDisplay(data.totalChildCount)} children; the space after the last loaded
          block is marked as not loaded
        </p>
      )}

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
            onCreateFromFreeBlock={setSelectedFreeBlock}
          />
        ))}
      </div>

      <IpPrefixTreeMapLegend isCapped={data.isCapped} />

      <IpPrefixCreateSheet
        schema={parentSchema}
        prefix={selectedFreeBlock?.cidr}
        isOpen={selectedFreeBlock !== null}
        onOpenChange={(isOpen) => {
          if (!isOpen) setSelectedFreeBlock(null);
        }}
        onSuccess={() => {
          setSelectedFreeBlock(null);
          queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
        }}
      />
    </Col>
  );
}

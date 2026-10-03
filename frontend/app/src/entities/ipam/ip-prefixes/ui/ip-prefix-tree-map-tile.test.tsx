import { describe, expect, it } from "vitest";

import { IpPrefixTreeMapTile } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-tile";
import { PERMISSION_ALLOW_ALL } from "@/entities/permission/domain/model/permission";

import { render } from "../../../../../tests/components/render";
import {
  generateAggregateAllocatedTile,
  generateAggregateFreeTile,
  generateAllocatedTile,
  generateFreeTile,
  generateRemainderTile,
  generateTreeMapRect,
} from "../../../../../tests/fake/ip-prefix-tree-map";

const PARENT = { id: "parent-id", kind: "IpamIPPrefix", cidr: "10.0.0.0/8" };

const noop = () => {};

describe("IpPrefixTreeMapTile", () => {
  it.each([0, 50, 100])("names an allocated tile at %d percent utilised", async (utilization) => {
    // GIVEN
    const rect = generateTreeMapRect({
      tile: generateAllocatedTile({ child: { cidr: "10.1.0.0/16", utilization } }),
    });

    // WHEN
    const component = await render(
      <IpPrefixTreeMapTile
        rect={rect}
        parent={PARENT}
        permission={PERMISSION_ALLOW_ALL}
        onCreateFromFreeBlock={noop}
      />
    );

    // THEN
    await expect
      .element(component.getByRole("link", { name: `10.1.0.0/16, ${utilization}% utilised` }))
      .toBeVisible();
  });

  it.each([0, 50, 100])(
    "fills an allocated tile to %d percent of its width",
    async (utilization) => {
      // GIVEN
      const rect = generateTreeMapRect({
        tile: generateAllocatedTile({ child: { cidr: "10.1.0.0/16", utilization } }),
      });

      // WHEN
      const component = await render(
        <IpPrefixTreeMapTile
          rect={rect}
          parent={PARENT}
          permission={PERMISSION_ALLOW_ALL}
          onCreateFromFreeBlock={noop}
        />
      );

      // THEN
      await expect
        .element(component.getByTestId("ip-prefix-tree-map-tile-fill"))
        .toHaveAttribute("style", expect.stringContaining(`width: ${utilization}%`));
    }
  );

  it("names an allocated tile with unknown utilisation", async () => {
    // GIVEN
    const rect = generateTreeMapRect({
      tile: generateAllocatedTile({ child: { cidr: "10.1.0.0/16", utilization: null } }),
    });

    // WHEN
    const component = await render(
      <IpPrefixTreeMapTile
        rect={rect}
        parent={PARENT}
        permission={PERMISSION_ALLOW_ALL}
        onCreateFromFreeBlock={noop}
      />
    );

    // THEN
    await expect
      .element(component.getByRole("link", { name: "10.1.0.0/16, utilisation unknown" }))
      .toBeVisible();
  });

  it("renders no fill when the utilisation is unknown", async () => {
    // GIVEN
    const rect = generateTreeMapRect({
      tile: generateAllocatedTile({ child: { cidr: "10.1.0.0/16", utilization: null } }),
    });

    // WHEN
    const component = await render(
      <IpPrefixTreeMapTile
        rect={rect}
        parent={PARENT}
        permission={PERMISSION_ALLOW_ALL}
        onCreateFromFreeBlock={noop}
      />
    );

    // THEN
    await expect
      .element(component.getByTestId("ip-prefix-tree-map-tile-fill"))
      .not.toBeInTheDocument();
  });

  it("exposes a free tile as a button named with its CIDR", async () => {
    // GIVEN
    const rect = generateTreeMapRect({
      tile: generateFreeTile({ block: { cidr: "10.3.0.0/16" } }),
    });

    // WHEN
    const component = await render(
      <IpPrefixTreeMapTile
        rect={rect}
        parent={PARENT}
        permission={PERMISSION_ALLOW_ALL}
        onCreateFromFreeBlock={noop}
      />
    );

    // THEN
    await expect
      .element(component.getByRole("button", { name: "10.3.0.0/16 available" }))
      .toBeVisible();
  });

  it.each([
    { kind: "allocated", tile: generateAllocatedTile() },
    { kind: "free", tile: generateFreeTile() },
    { kind: "aggregate-allocated", tile: generateAggregateAllocatedTile() },
    { kind: "aggregate-free", tile: generateAggregateFreeTile() },
    { kind: "remainder", tile: generateRemainderTile() },
  ])("marks a $kind tile with its test id and tile kind", async ({ kind, tile }) => {
    // GIVEN
    const rect = generateTreeMapRect({ tile });

    // WHEN
    const component = await render(
      <IpPrefixTreeMapTile
        rect={rect}
        parent={PARENT}
        permission={PERMISSION_ALLOW_ALL}
        onCreateFromFreeBlock={noop}
      />
    );

    // THEN
    await expect
      .element(component.getByTestId("ip-prefix-tree-map-tile"))
      .toHaveAttribute("data-tile-kind", kind);
  });
});

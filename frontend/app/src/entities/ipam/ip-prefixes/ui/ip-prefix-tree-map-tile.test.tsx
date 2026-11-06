import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { store } from "@/shared/stores";

import type { TreeMapFreeBlock } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";
import { IpPrefixTreeMapTile } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-tile";
import {
  PERMISSION_ALLOW_ALL,
  PERMISSION_DENY_ALL,
  type Permission,
} from "@/entities/permission/domain/model/permission";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../tests/components/utils";
import {
  generateAggregateAllocatedTile,
  generateAggregateFreeTile,
  generateAllocatedTile,
  generateFreeTile,
  generateNotLoadedTile,
  generateTreeMapChild,
  generateTreeMapFreeBlock,
  generateTreeMapRect,
} from "../../../../../tests/fake/ip-prefix-tree-map";
import { generateNodeSchema } from "../../../../../tests/fake/schema";

const PARENT = { id: "parent-id", kind: "IpamIPPrefix", cidr: "10.0.0.0/8" };

const noop = () => {};

const generateSlash24Children = (count: number) =>
  Array.from({ length: count }, (_, index) => generateTreeMapChild({ cidr: `10.0.${index}.0/24` }));

const initialNodeSchemas = store.get(nodeSchemasAtom);

beforeAll(() => {
  store.set(nodeSchemasAtom, [
    generateNodeSchema({ kind: "IpamIPPrefix", inherit_from: ["BuiltinIPPrefix"] }),
  ]);
});

afterAll(() => {
  store.set(nodeSchemasAtom, initialNodeSchemas);
});

afterEach(() => {
  window.history.replaceState(null, "", window.location.pathname);
});

describe("IpPrefixTreeMapTile", () => {
  it("links an allocated tile to the child's tree map in the current namespace", async () => {
    // GIVEN
    window.history.replaceState(null, "", "?namespace=abc");
    const rect = generateTreeMapRect({
      tile: generateAllocatedTile({
        child: { id: "child-id", kind: "IpamIPPrefix", cidr: "10.1.0.0/16" },
      }),
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
      .element(component.getByRole("link", { name: "10.1.0.0/16, 0% utilized" }))
      .toHaveAttribute("href", "/ipam/IpamIPPrefix/child-id/tree-map?namespace=abc");
  });

  it("links an aggregate tile to the parent's children in the current namespace", async () => {
    // GIVEN
    window.history.replaceState(null, "", "?namespace=abc");
    const rect = generateTreeMapRect({ tile: generateAggregateAllocatedTile() });

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
      .element(component.getByRole("link", { name: "10.0.0.0/20: 1 smaller prefix" }))
      .toHaveAttribute("href", "/ipam/IpamIPPrefix/parent-id/children?namespace=abc");
  });

  it("keeps the branch and namespace params on an allocated tile's link", async () => {
    // GIVEN
    window.history.replaceState(null, "", "?branch=feature&namespace=abc");
    const rect = generateTreeMapRect({
      tile: generateAllocatedTile({
        child: { id: "child-id", kind: "IpamIPPrefix", cidr: "10.1.0.0/16" },
      }),
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
    const link = component.getByRole("link", { name: "10.1.0.0/16, 0% utilized" });
    await expect.element(link).toHaveAttribute("href", expect.stringContaining("branch=feature"));
    await expect.element(link).toHaveAttribute("href", expect.stringContaining("namespace=abc"));
  });

  it("shows the child's details when hovering an allocated tile", async () => {
    // GIVEN
    const component = await render(
      <div className="relative h-64 w-96">
        <IpPrefixTreeMapTile
          rect={generateTreeMapRect({
            tile: generateAllocatedTile({
              child: {
                cidr: "10.1.0.0/16",
                description: "Interconnections",
                memberType: "prefix",
                utilization: 50,
                memberCount: 16,
              },
            }),
          })}
          parent={PARENT}
          permission={PERMISSION_ALLOW_ALL}
          onCreateFromFreeBlock={noop}
        />
      </div>
    );
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByRole("link", { name: "10.1.0.0/16, 50% utilized" }).hover();

    // THEN
    const tooltip = component.getByRole("tooltip");
    await expect.element(tooltip).toHaveTextContent("10.1.0.0/16");
    await expect.element(tooltip).toHaveTextContent("Interconnections");
    await expect.element(tooltip).toHaveTextContent("Member type: prefix");
    await expect.element(tooltip).toHaveTextContent("50% utilized");
    await expect.element(tooltip).toHaveTextContent("16 child prefixes");
    await initPointerTracking(component.locator);
  });

  it("shows the CIDR when hovering a free tile", async () => {
    // GIVEN
    const component = await render(
      <div className="relative h-64 w-96">
        <IpPrefixTreeMapTile
          rect={generateTreeMapRect({
            tile: generateFreeTile({ block: generateTreeMapFreeBlock({ cidr: "10.3.0.0/16" }) }),
          })}
          parent={PARENT}
          permission={PERMISSION_ALLOW_ALL}
          onCreateFromFreeBlock={noop}
        />
      </div>
    );
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByRole("button", { name: "10.3.0.0/16 available" }).hover();

    // THEN
    await expect.element(component.getByRole("tooltip")).toHaveTextContent("10.3.0.0/16");
    await initPointerTracking(component.locator);
  });

  it("styles a pool child with the pool surface and marks the tile as a pool", async () => {
    // GIVEN
    const rect = generateTreeMapRect({
      tile: generateAllocatedTile({ child: { cidr: "10.1.0.0/16", isPool: true } }),
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
      .element(component.getByRole("link", { name: "10.1.0.0/16, 0% utilized, pool" }))
      .toHaveClass(/bg-pool-surface/);
    await expect
      .element(component.getByTestId("ip-prefix-tree-map-tile"))
      .toHaveAttribute("data-tile-pool", "true");
  });

  it("shows the description on its own line when the tile is wide enough", async () => {
    // GIVEN
    const component = await render(
      <div className="relative h-40 w-96">
        <IpPrefixTreeMapTile
          rect={generateTreeMapRect({
            x: 0,
            y: 0,
            width: 100,
            height: 100,
            tile: generateAllocatedTile({
              child: { cidr: "10.1.0.0/16", description: "Interconnections" },
            }),
          })}
          parent={PARENT}
          permission={PERMISSION_ALLOW_ALL}
          onCreateFromFreeBlock={noop}
        />
      </div>
    );

    // WHEN the tile is laid out at 24rem wide
    const description = component.getByText("Interconnections");

    // THEN the description is visible and the marker is not
    await expect.element(description).toBeVisible();
    await expect
      .element(component.getByTestId("ip-prefix-tree-map-tile-description-marker"))
      .not.toBeVisible();
  });

  it("marks that a description exists when the tile is too narrow to show it", async () => {
    // GIVEN
    const component = await render(
      <div className="relative h-40 w-32">
        <IpPrefixTreeMapTile
          rect={generateTreeMapRect({
            x: 0,
            y: 0,
            width: 100,
            height: 100,
            tile: generateAllocatedTile({
              child: { cidr: "10.1.0.0/16", description: "Interconnections" },
            }),
          })}
          parent={PARENT}
          permission={PERMISSION_ALLOW_ALL}
          onCreateFromFreeBlock={noop}
        />
      </div>
    );

    // WHEN the tile is laid out at 8rem wide
    const marker = component.getByTestId("ip-prefix-tree-map-tile-description-marker");

    // THEN the marker shows and the description text stays hidden
    await expect.element(marker).toBeVisible();
    await expect.element(component.getByText("Interconnections")).not.toBeVisible();
  });

  it.each([0, 50, 100])("names an allocated tile at %d percent utilized", async (utilization) => {
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
      .element(component.getByRole("link", { name: `10.1.0.0/16, ${utilization}% utilized` }))
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

  it("names an allocated tile with unknown utilization", async () => {
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
      .element(component.getByRole("link", { name: "10.1.0.0/16, utilization unknown" }))
      .toBeVisible();
  });

  it("renders no fill when the utilization is unknown", async () => {
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

  it("calls the create handler with the free block when its button is clicked", async () => {
    // GIVEN
    const block = generateTreeMapFreeBlock({ cidr: "10.3.0.0/16" });
    const createdFrom: TreeMapFreeBlock[] = [];
    const component = await render(
      <IpPrefixTreeMapTile
        rect={generateTreeMapRect({ tile: generateFreeTile({ block }) })}
        parent={PARENT}
        permission={PERMISSION_ALLOW_ALL}
        onCreateFromFreeBlock={(selected) => createdFrom.push(selected)}
      />
    );

    // WHEN
    await component.getByRole("button", { name: "10.3.0.0/16 available" }).click();

    // THEN
    expect(createdFrom).toEqual([block]);
  });

  it("disables the free tile button when creating prefixes is not allowed", async () => {
    // GIVEN
    const rect = generateTreeMapRect({
      tile: generateFreeTile({ block: { cidr: "10.3.0.0/16" } }),
    });

    // WHEN
    const component = await render(
      <IpPrefixTreeMapTile
        rect={rect}
        parent={PARENT}
        permission={PERMISSION_DENY_ALL}
        onCreateFromFreeBlock={noop}
      />
    );

    // THEN
    await expect
      .element(component.getByRole("button", { name: "10.3.0.0/16 available" }))
      .toHaveAttribute("aria-disabled", "true");
  });

  it("does not call the create handler from a disabled free tile", async () => {
    // GIVEN
    const createdFrom: TreeMapFreeBlock[] = [];
    const component = await render(
      <IpPrefixTreeMapTile
        rect={generateTreeMapRect({ tile: generateFreeTile({ block: { cidr: "10.3.0.0/16" } }) })}
        parent={PARENT}
        permission={PERMISSION_DENY_ALL}
        onCreateFromFreeBlock={(selected) => createdFrom.push(selected)}
      />
    );

    // WHEN
    await component.getByRole("button", { name: "10.3.0.0/16 available" }).click({ force: true });

    // THEN
    expect(createdFrom).toEqual([]);
  });

  it("shows the permission message when hovering a disabled free tile", async () => {
    // GIVEN
    const permission: Permission = {
      ...PERMISSION_DENY_ALL,
      create: { isAllowed: false, message: "You need the create permission on IP prefixes" },
    };
    // A sized map container gives the pointer warm-up click a visible target.
    const component = await render(
      <div className="relative h-64 w-96">
        <IpPrefixTreeMapTile
          rect={generateTreeMapRect({ tile: generateFreeTile({ block: { cidr: "10.3.0.0/16" } }) })}
          parent={PARENT}
          permission={permission}
          onCreateFromFreeBlock={noop}
        />
      </div>
    );
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByRole("button", { name: "10.3.0.0/16 available" }).hover();

    // THEN
    await expect
      .element(
        component.getByRole("tooltip", {
          name: "You need the create permission on IP prefixes",
        })
      )
      .toBeVisible();
    await initPointerTracking(component.locator);
  });

  it("names an aggregate of three allocated prefixes as a link", async () => {
    // GIVEN
    const rect = generateTreeMapRect({
      tile: generateAggregateAllocatedTile({ children: generateSlash24Children(3) }),
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
      .element(component.getByRole("link", { name: "10.0.0.0/20: 3 smaller prefixes" }))
      .toBeVisible();
  });

  it("lists the member CIDRs when hovering an aggregate of three allocated prefixes", async () => {
    // GIVEN
    const component = await render(
      <div className="relative h-64 w-96">
        <IpPrefixTreeMapTile
          rect={generateTreeMapRect({
            tile: generateAggregateAllocatedTile({ children: generateSlash24Children(3) }),
          })}
          parent={PARENT}
          permission={PERMISSION_ALLOW_ALL}
          onCreateFromFreeBlock={noop}
        />
      </div>
    );
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByRole("link", { name: "10.0.0.0/20: 3 smaller prefixes" }).hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip"))
      .toHaveTextContent("10.0.0.0/24, 10.0.1.0/24, 10.0.2.0/24");
    await initPointerTracking(component.locator);
  });

  it("truncates the member list after twenty CIDRs when hovering a large aggregate", async () => {
    // GIVEN
    const members = generateSlash24Children(25);
    const component = await render(
      <div className="relative h-64 w-96">
        <IpPrefixTreeMapTile
          rect={generateTreeMapRect({
            tile: generateAggregateAllocatedTile({ children: members }),
          })}
          parent={PARENT}
          permission={PERMISSION_ALLOW_ALL}
          onCreateFromFreeBlock={noop}
        />
      </div>
    );
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByRole("link", { name: "10.0.0.0/20: 25 smaller prefixes" }).hover();

    // THEN
    const shownMembers = members.slice(0, 20).map((member) => member.cidr);
    await expect
      .element(component.getByRole("tooltip"))
      .toHaveTextContent(`${shownMembers.join(", ")} and 5 more`);
    await expect.element(component.getByRole("tooltip")).not.toHaveTextContent("10.0.20.0/24");
    await initPointerTracking(component.locator);
  });

  it("names a not-loaded tile after the block it covers", async () => {
    // GIVEN
    const rect = generateTreeMapRect({
      tile: generateNotLoadedTile({ cidr: "10.128.0.0/9", hiddenChildCount: 200 }),
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
      .element(component.getByRole("link", { name: "10.128.0.0/9 not loaded" }))
      .toHaveAttribute("href", "/ipam/IpamIPPrefix/parent-id/children");
  });

  it("exposes an aggregate of free blocks as a non-interactive image", async () => {
    // GIVEN
    const rect = generateTreeMapRect({
      tile: generateAggregateFreeTile({
        cidr: "10.0.0.0/20",
        freeBlocks: ["10.0.1.0/24", "10.0.2.0/24"].map((cidr) =>
          generateTreeMapFreeBlock({ cidr })
        ),
      }),
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
      .element(component.getByRole("img", { name: "10.0.0.0/20: 2 smaller free blocks" }))
      .toBeVisible();
    await expect.element(component.getByRole("link")).not.toBeInTheDocument();
    await expect.element(component.getByRole("button")).not.toBeInTheDocument();
  });

  it.each([
    { kind: "allocated", tile: generateAllocatedTile() },
    { kind: "free", tile: generateFreeTile() },
    { kind: "aggregate-allocated", tile: generateAggregateAllocatedTile() },
    { kind: "aggregate-free", tile: generateAggregateFreeTile() },
    { kind: "not-loaded", tile: generateNotLoadedTile() },
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

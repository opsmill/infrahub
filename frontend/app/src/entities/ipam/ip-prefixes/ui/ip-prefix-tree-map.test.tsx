import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { store } from "@/shared/stores";

import { getIpPrefixTreeMap } from "@/entities/ipam/ip-prefixes/domain/use-cases/get-ip-prefix-tree-map";
import { IpPrefixTreeMap } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map";
import { PERMISSION_ALLOW_ALL } from "@/entities/permission/domain/model/permission";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import {
  generateSlash18ChildrenOfDemoSupernet,
  generateTreeMapParent,
} from "../../../../../tests/fake/ip-prefix-tree-map";
import { generateNodeSchema } from "../../../../../tests/fake/schema";

vi.mock("@/entities/ipam/ip-prefixes/domain/use-cases/get-ip-prefix-tree-map");

const PARENT_SCHEMA = generateNodeSchema({
  kind: "IpamIPPrefix",
  inherit_from: ["BuiltinIPPrefix"],
});

const initialNodeSchemas = store.get(nodeSchemasAtom);

beforeAll(() => {
  store.set(nodeSchemasAtom, [PARENT_SCHEMA]);
});

afterAll(() => {
  store.set(nodeSchemasAtom, initialNodeSchemas);
});

afterEach(() => {
  vi.resetAllMocks();
});

describe("IpPrefixTreeMap", () => {
  it("announces how many children are shown when the parent has more than the cap", async () => {
    // GIVEN
    vi.mocked(getIpPrefixTreeMap).mockResolvedValue({
      children: generateSlash18ChildrenOfDemoSupernet(1000),
      freeBlocks: [],
      totalChildCount: 1200,
      isCapped: true,
    });

    // WHEN
    const component = await render(
      <IpPrefixTreeMap
        parent={{ ...generateTreeMapParent({ cidr: "10.0.0.0/8" }), kind: "IpamIPPrefix" }}
        parentSchema={PARENT_SCHEMA}
        permission={PERMISSION_ALLOW_ALL}
      />
    );

    // THEN
    await expect
      .element(component.getByRole("status"))
      .toHaveTextContent("Showing the first 1,000 of 1,200 children");
  });

  it("shows no cap notice when every child fits in the map", async () => {
    // GIVEN
    vi.mocked(getIpPrefixTreeMap).mockResolvedValue({
      children: generateSlash18ChildrenOfDemoSupernet(2),
      freeBlocks: [],
      totalChildCount: 2,
      isCapped: false,
    });

    // WHEN
    const component = await render(
      <IpPrefixTreeMap
        parent={{ ...generateTreeMapParent({ cidr: "10.0.0.0/8" }), kind: "IpamIPPrefix" }}
        parentSchema={PARENT_SCHEMA}
        permission={PERMISSION_ALLOW_ALL}
      />
    );

    // THEN
    await expect
      .element(component.getByRole("group", { name: "Tree map of 10.0.0.0/8" }))
      .toBeVisible();
    await expect.element(component.getByRole("status")).not.toBeInTheDocument();
  });

  it("shows the empty state for an address prefix with no child prefixes", async () => {
    // GIVEN
    vi.mocked(getIpPrefixTreeMap).mockResolvedValue({
      children: [],
      freeBlocks: [],
      totalChildCount: 0,
      isCapped: false,
    });

    // WHEN
    const component = await render(
      <IpPrefixTreeMap
        parent={{
          ...generateTreeMapParent({ cidr: "10.0.0.0/16", memberType: "address", utilization: 12 }),
          kind: "IpamIPPrefix",
        }}
        parentSchema={PARENT_SCHEMA}
        permission={PERMISSION_ALLOW_ALL}
      />
    );

    // THEN
    await expect.element(component.getByTestId("ip-prefix-tree-map-empty")).toBeVisible();
    await expect.element(component.getByTestId("ip-prefix-tree-map")).not.toBeInTheDocument();
  });

  it("shows the map for an address prefix that still holds child prefixes", async () => {
    // GIVEN
    vi.mocked(getIpPrefixTreeMap).mockResolvedValue({
      children: generateSlash18ChildrenOfDemoSupernet(3),
      freeBlocks: [],
      totalChildCount: 3,
      isCapped: false,
    });

    // WHEN
    const component = await render(
      <IpPrefixTreeMap
        parent={{
          ...generateTreeMapParent({ cidr: "10.0.0.0/8", memberType: "address" }),
          kind: "IpamIPPrefix",
        }}
        parentSchema={PARENT_SCHEMA}
        permission={PERMISSION_ALLOW_ALL}
      />
    );

    // THEN
    await expect
      .element(component.getByRole("group", { name: "Tree map of 10.0.0.0/8" }))
      .toBeVisible();
    await expect.element(component.getByTestId("ip-prefix-tree-map-empty")).not.toBeInTheDocument();
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";

import { Component as IpamDetailsPage } from "@/pages/ipam/ipam-details-page";

import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { render } from "../../../tests/components/render";
import {
  generateNodeAttributeWithMetadata,
  generateRelationshipNodeWithMetadata,
} from "../../../tests/fake/node";
import { generatePermission } from "../../../tests/fake/permission";
import {
  generateAttributeSchema,
  generateContainerSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../tests/fake/schema";

vi.mock("react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router")>()),
  useParams: () => ({ objectKind: "IpamIPPrefix", objectId: "prefix-1" }),
}));
vi.mock("@/entities/schema/ui/hooks/useSchema");
vi.mock("@/entities/nodes/object/ui/queries/get-object.query");
vi.mock("@/entities/permission/ui/queries/get-object-permissions.query");
vi.mock("@/entities/nodes/object/ui/object-details/object-profiles-groups-card", () => ({
  ObjectProfilesGroupsCard: () => null,
}));
vi.mock("@/entities/nodes/object/ui/object-details/object-activities-card", () => ({
  ObjectActivitiesCard: () => null,
}));

const prefixSchema = generateNodeSchema({
  kind: "IpamIPPrefix",
  name: "IPPrefix",
  namespace: "Ipam",
  label: "IP Prefix",
  inherit_from: ["BuiltinIPPrefix"],
  containers: [generateContainerSchema({ name: "routing", label: "Routing" })],
  attributes: [
    generateAttributeSchema({ name: "prefix", label: "Prefix", order_weight: 1000 }),
    generateAttributeSchema({
      name: "vrf_target",
      label: "VRF target",
      order_weight: 2000,
      container: "routing",
    }),
    generateAttributeSchema({
      name: "internal_id",
      label: "Internal ID",
      order_weight: 3000,
      container: "advanced",
    }),
  ],
  relationships: [
    generateRelationshipSchema({
      name: "children",
      label: "Children",
      peer: "IpamIPPrefix",
      kind: "Attribute",
      cardinality: "one",
      order_weight: 4000,
      container: "routing",
    }),
  ],
});

const prefixData: NodeObjectWithMetadata = {
  id: "prefix-1",
  display_label: "10.0.0.0/8",
  __typename: "IpamIPPrefix",
  prefix: generateNodeAttributeWithMetadata({ value: "10.0.0.0/8" }),
  vrf_target: generateNodeAttributeWithMetadata({ value: "65000:1" }),
  internal_id: generateNodeAttributeWithMetadata({ value: "int-42" }),
  children: generateRelationshipNodeWithMetadata({
    node: { id: "prefix-2", display_label: "10.1.0.0/16", __typename: "IpamIPPrefix" },
  }),
};

beforeEach(() => {
  vi.mocked(useSchema).mockReturnValue({ schema: prefixSchema } as unknown as ReturnType<
    typeof useSchema
  >);
  vi.mocked(useGetObject).mockReturnValue({
    isPending: false,
    error: null,
    data: prefixData,
  } as unknown as ReturnType<typeof useGetObject>);
  vi.mocked(useGetObjectPermissions).mockReturnValue({
    isPending: false,
    error: null,
    data: generatePermission(),
  } as unknown as ReturnType<typeof useGetObjectPermissions>);
});

describe("IPAM details page", () => {
  it("renders the sections of a prefix schema and leaves out the excluded relationships", async () => {
    const component = await render(<IpamDetailsPage />);

    const details = component.getByRole("region", { name: "Details" });
    const routing = component.getByRole("region", { name: "Routing" });
    await expect.element(details.getByText("Prefix", { exact: true })).toBeVisible();
    await expect.element(routing.getByText("VRF target", { exact: true })).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Advanced" }))
      .toHaveAttribute("aria-expanded", "false");
    expect(details.getByText("VRF target", { exact: true }).elements()).toHaveLength(0);
    expect(component.getByText("Children", { exact: true }).elements()).toHaveLength(0);
  });
});

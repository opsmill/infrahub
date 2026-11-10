import { beforeEach, describe, expect, it, vi } from "vitest";

import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { ObjectDetails } from "@/entities/nodes/object/ui/object-details/object-details";
import { getRepositoryBranchStatus } from "@/entities/repository/domain/use-cases/get-repository-branch-status";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

import { render } from "../../../../../../tests/components/render";
import {
  generateNodeAttributeWithMetadata,
  generateRelationshipNodeWithMetadata,
} from "../../../../../../tests/fake/node";
import { generatePermission } from "../../../../../../tests/fake/permission";
import {
  generateAttributeSchema,
  generateContainerSchema,
  generateNodeSchema,
  generateProfileSchema,
  generateRelationshipSchema,
  generateTemplateSchema,
} from "../../../../../../tests/fake/schema";

vi.mock("@/entities/repository/domain/use-cases/get-repository-branch-status");
vi.mock("@/entities/repository/ui/repository-push-to-remote-card", () => ({
  RepositoryPushToRemoteCard: () => <p>Push to remote</p>,
}));

const branchStatusMock = vi.mocked(getRepositoryBranchStatus);

const permission = generatePermission();

const attributes = [
  generateAttributeSchema({ name: "name", label: "Name", branch: "agnostic", order_weight: 1000 }),
  generateAttributeSchema({ name: "commit", label: "Commit", branch: "local", order_weight: 2000 }),
];

const tagSchema: ModelSchema = generateNodeSchema({
  kind: "BuiltinTag",
  name: "Tag",
  namespace: "Builtin",
  label: "Tag",
  branch: "aware",
  inherit_from: [],
  attributes,
  relationships: [],
});

const repositorySchema: ModelSchema = generateNodeSchema({
  kind: "CoreRepository",
  name: "Repository",
  namespace: "Core",
  label: "Repository",
  branch: "agnostic",
  inherit_from: ["CoreGenericRepository"],
  attributes,
  relationships: [],
});

const readOnlyRepositorySchema: ModelSchema = generateNodeSchema({
  ...repositorySchema,
  kind: "CoreReadOnlyRepository",
  name: "ReadOnlyRepository",
  label: "Read-only repository",
});

const objectData: NodeObjectWithMetadata = {
  id: "object-1",
  display_label: "demo-object",
  __typename: "BuiltinTag",
  name: generateNodeAttributeWithMetadata({ value: "demo-object" }),
  commit: generateNodeAttributeWithMetadata({ value: "abc1234" }),
};

beforeEach(() => {
  branchStatusMock.mockResolvedValue({ rows: [], count: 0 });
});

describe("ObjectDetails repository kind gate", () => {
  it("renders a single details card for a non-repository kind", async () => {
    const component = await render(
      <ObjectDetails objectSchema={tagSchema} objectData={objectData} permission={permission} />
    );

    await expect.element(component.getByText("Details", { exact: true })).toBeVisible();
    await expect.element(component.getByText("Name", { exact: true })).toBeVisible();
    await expect.element(component.getByText("Commit", { exact: true })).toBeVisible();

    expect(component.getByText("Details", { exact: true }).elements()).toHaveLength(1);
    expect(component.getByText("On this branch", { exact: true }).elements()).toHaveLength(0);
    expect(component.getByRole("region", { name: "Details" }).elements()).toHaveLength(1);
  });

  it("renders the two-card split for the read-write repository kind", async () => {
    const component = await render(
      <ObjectDetails
        objectSchema={repositorySchema}
        objectData={{ ...objectData, __typename: "CoreRepository" }}
        permission={permission}
      />
    );

    await expect.element(component.getByRole("region", { name: "Details" })).toBeVisible();
    await expect
      .element(component.getByRole("region", { name: "On this branch test-branch" }))
      .toBeVisible();
  });

  it("renders the two-card split for a kind that inherits from the repository generic", async () => {
    const component = await render(
      <ObjectDetails
        objectSchema={readOnlyRepositorySchema}
        objectData={{ ...objectData, __typename: "CoreReadOnlyRepository" }}
        permission={permission}
      />
    );

    await expect.element(component.getByRole("region", { name: "Details" })).toBeVisible();
    await expect
      .element(component.getByRole("region", { name: "On this branch test-branch" }))
      .toBeVisible();
  });
});

const sectionedAttributes = [
  generateAttributeSchema({ name: "name", label: "Name", order_weight: 1000 }),
  generateAttributeSchema({
    name: "lag_mode",
    label: "LAG mode",
    order_weight: 2000,
    container: "lacp",
  }),
  generateAttributeSchema({
    name: "lacp_rate",
    label: "LACP rate",
    order_weight: 3000,
    container: "lacp",
    display: "extra",
  }),
  generateAttributeSchema({
    name: "ip_address",
    label: "IP address",
    order_weight: 4000,
    container: "addressing",
  }),
  generateAttributeSchema({
    name: "internal_id",
    label: "Internal ID",
    order_weight: 5000,
    container: "management",
  }),
];

const sectionedRelationships = [
  generateRelationshipSchema({
    name: "site",
    label: "Site",
    peer: "LocationSite",
    kind: "Attribute",
    cardinality: "one",
    order_weight: 6000,
    container: "addressing",
  }),
  generateRelationshipSchema({
    name: "member_of_groups",
    label: "Groups",
    peer: "CoreGroup",
    kind: "Group",
    cardinality: "many",
    order_weight: 7000,
    container: "membership",
  }),
];

const sectionContainers = [
  generateContainerSchema({ name: "lacp", label: "LACP", order_weight: 2000 }),
  generateContainerSchema({
    name: "addressing",
    label: "Addressing",
    order_weight: 1000,
    description: "Where the interface sits on the network",
  }),
  generateContainerSchema({ name: "membership", label: "Membership", order_weight: 3000 }),
  generateContainerSchema({
    name: "management",
    label: "Management",
    order_weight: 4000,
    collapsed: true,
  }),
];

const sectionedSchema: ModelSchema = generateNodeSchema({
  kind: "InfraInterface",
  name: "Interface",
  namespace: "Infra",
  label: "Interface",
  inherit_from: [],
  containers: sectionContainers,
  attributes: sectionedAttributes,
  relationships: sectionedRelationships,
});

const sectionedData: NodeObjectWithMetadata = {
  id: "interface-1",
  display_label: "eth0",
  __typename: "InfraInterface",
  name: generateNodeAttributeWithMetadata({ value: "eth0" }),
  lag_mode: generateNodeAttributeWithMetadata({ value: "active" }),
  lacp_rate: generateNodeAttributeWithMetadata({ value: "fast" }),
  ip_address: generateNodeAttributeWithMetadata({ value: "10.0.0.1/24" }),
  internal_id: generateNodeAttributeWithMetadata({ value: "int-42" }),
  site: generateRelationshipNodeWithMetadata({
    node: { id: "site-1", display_label: "Paris", __typename: "LocationSite" },
  }),
  member_of_groups: { edges: [] },
};

const SECTION_ORDER = ["Details", "Addressing", "LACP", "Management"];

async function expectSectionsInOrder(component: Awaited<ReturnType<typeof render>>) {
  const regions = [];
  for (const name of SECTION_ORDER) {
    const locator = component.getByRole("region", { name });
    await expect.element(locator).toBeInTheDocument();
    regions.push(locator.element());
  }
  for (let index = 1; index < regions.length; index++) {
    expect(regions[index - 1]!.compareDocumentPosition(regions[index]!)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING
    );
  }
  expect(component.getByTestId("object-details").elements()).toEqual([regions[0]]);
  expect(
    component
      .getByTestId("object-details-section")
      .elements()
      .map((card) => card.getAttribute("data-section"))
  ).toEqual(["addressing", "lacp", "management"]);
  expect(component.getByRole("region", { name: "Membership" }).elements()).toHaveLength(0);
}

describe("ObjectDetails sections", () => {
  it("renders Details then the containers by order weight", async () => {
    const component = await render(
      <ObjectDetails
        objectSchema={sectionedSchema}
        objectData={sectionedData}
        permission={permission}
      />
    );

    await expectSectionsInOrder(component);
  });

  it("renders each field once", async () => {
    const component = await render(
      <ObjectDetails
        objectSchema={sectionedSchema}
        objectData={sectionedData}
        permission={permission}
      />
    );

    await component.getByRole("button", { name: "Management" }).click();

    for (const label of ["Name", "LAG mode", "IP address", "Site", "Internal ID"]) {
      await expect.element(component.getByText(label, { exact: true })).toBeVisible();
      expect(component.getByText(label, { exact: true }).elements()).toHaveLength(1);
    }
    await expect
      .element(
        component.getByRole("region", { name: "Addressing" }).getByRole("link", { name: "site-1" })
      )
      .toBeVisible();
    await expect
      .element(component.getByRole("region", { name: "LACP" }).getByText("LAG mode"))
      .toBeVisible();
  });

  it("shows the Extra button only on the section with an extra field", async () => {
    const component = await render(
      <ObjectDetails
        objectSchema={sectionedSchema}
        objectData={sectionedData}
        permission={permission}
      />
    );

    const lacp = component.getByRole("region", { name: "LACP" });
    await expect.element(lacp.getByRole("button", { name: "Extra" })).toBeVisible();
    expect(component.getByRole("button", { name: "Extra" }).elements()).toHaveLength(1);

    // WHEN
    await lacp.getByRole("button", { name: "Extra" }).click();

    // THEN
    await expect.element(lacp.getByText("LACP rate", { exact: true })).toBeVisible();
  });

  it("starts a card collapsed when its container is collapsed", async () => {
    const component = await render(
      <ObjectDetails
        objectSchema={sectionedSchema}
        objectData={sectionedData}
        permission={permission}
      />
    );

    await expect
      .element(component.getByRole("button", { name: "Management" }))
      .toHaveAttribute("aria-expanded", "false");
    await expect
      .element(component.getByRole("button", { name: "LACP" }))
      .toHaveAttribute("aria-expanded", "true");
    await expect.element(component.getByText("Internal ID", { exact: true })).not.toBeVisible();
  });

  it("renders a single Details region for a schema without containers", async () => {
    const schemaWithoutContainers = generateNodeSchema({
      ...sectionedSchema,
      containers: [],
      attributes: sectionedAttributes.map((attribute) => ({ ...attribute, container: null })),
      relationships: sectionedRelationships.map((relationship) => ({
        ...relationship,
        container: null,
      })),
    });

    const component = await render(
      <ObjectDetails
        objectSchema={schemaWithoutContainers}
        objectData={sectionedData}
        permission={permission}
      />
    );

    await expect.element(component.getByRole("region", { name: "Details" })).toBeVisible();
    expect(component.getByTestId("object-details").elements()).toHaveLength(1);
    expect(component.getByRole("button", { name: "Details" }).elements()).toHaveLength(0);
  });

  it("shows a pool-allocated attribute inside a section with its pool row", async () => {
    const schemaWithPool = generateNodeSchema({
      ...sectionedSchema,
      attributes: [
        ...sectionedAttributes,
        generateAttributeSchema({
          name: "vlan_id",
          label: "VLAN ID",
          kind: "Number",
          order_weight: 2500,
          container: "lacp",
        }),
      ],
      relationships: [
        ...sectionedRelationships,
        generateRelationshipSchema({
          name: "vlan_id_from_resource_pool",
          label: "VLAN ID from pool",
          peer: "CoreNumberPool",
          kind: "Attribute",
          cardinality: "one",
          container: null,
        }),
      ],
    });
    const dataWithPool: NodeObjectWithMetadata = {
      ...sectionedData,
      vlan_id: generateNodeAttributeWithMetadata({ value: 100 }),
      vlan_id_from_resource_pool: generateRelationshipNodeWithMetadata({
        node: { id: "pool-1", display_label: "VLAN pool", __typename: "CoreNumberPool" },
      }),
    };

    const component = await render(
      <ObjectDetails
        objectSchema={schemaWithPool}
        objectData={dataWithPool}
        permission={permission}
      />
    );

    const lacp = component.getByRole("region", { name: "LACP" });
    await expect.element(lacp.getByText("VLAN ID", { exact: true })).toBeVisible();
    await expect.element(lacp.getByRole("link", { name: "pool-1" })).toBeVisible();
    expect(component.getByText("VLAN ID from pool").elements()).toHaveLength(0);
  });

  it.each([
    ["a profile", generateProfileSchema, "ProfileInfraInterface"],
    ["an object template", generateTemplateSchema, "TemplateInfraInterface"],
  ] as const)("renders the same sections for %s schema", async (_, generateSchema, typename) => {
    const component = await render(
      <ObjectDetails
        objectSchema={generateSchema({
          containers: sectionContainers,
          attributes: sectionedAttributes,
          relationships: sectionedRelationships,
        })}
        objectData={{ ...sectionedData, __typename: typename }}
        permission={permission}
      />
    );

    await expectSectionsInOrder(component);
  });
});

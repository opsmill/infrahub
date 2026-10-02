import { afterAll, beforeAll, beforeEach, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import type { NodeSchema } from "@/entities/schema/domain/model/schema";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../tests/components/render";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { RelationshipTable } from "./relationship-table";

vi.mock("@/entities/nodes/relationships/ui/queries/get-object-relationships.query", () => ({
  useObjectRelationships: vi.fn(),
}));
vi.mock("@/entities/nodes/relationships/ui/queries/get-relationship-count.query", () => ({
  useGetRelationshipCount: vi.fn(),
}));
vi.mock("@/entities/permission/ui/queries/get-object-permissions.query", () => ({
  useGetObjectPermissions: vi.fn(),
}));

import { useObjectRelationships } from "@/entities/nodes/relationships/ui/queries/get-object-relationships.query";
import { useGetRelationshipCount } from "@/entities/nodes/relationships/ui/queries/get-relationship-count.query";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";

const PARENT_KIND = "TestingDevice";
const PEER_KIND = "TestingInterface";
const RELATIONSHIP_NAME = "interfaces";
const DESCRIPTION_VALUE = "uplink to spine";

// `internal_note` is `display: "extra"`, so the relationship fetch path never selects it. It is the
// probe for the surface: the object surface would offer it, this one must not.
const peerSchema = generateNodeSchema({
  kind: PEER_KIND,
  name: "Interface",
  label: "Interface",
  attributes: [
    generateAttributeSchema({ name: "name", label: "Name", kind: "Text", order_weight: 1000 }),
    generateAttributeSchema({
      name: "description",
      label: "Description",
      kind: "Text",
      order_weight: 2000,
    }),
    generateAttributeSchema({
      name: "internal_note",
      label: "Internal note",
      kind: "Text",
      display: "extra",
      order_weight: 3000,
    }),
  ],
  relationships: [],
});

const parentSchema = generateNodeSchema({
  kind: PARENT_KIND,
  name: "Device",
  label: "Device",
  attributes: [],
  relationships: [
    generateRelationshipSchema({
      name: RELATIONSHIP_NAME,
      peer: PEER_KIND,
      kind: "Component",
      cardinality: "many",
    }),
  ],
});

const relationshipRows = [
  {
    id: "interface-1",
    __typename: PEER_KIND,
    display_label: "Ethernet1",
    name: { value: "Ethernet1" },
    description: { value: DESCRIPTION_VALUE },
    internal_note: { value: "not fetched here" },
  },
] as unknown as NodeObject[];

const seedColumnsInUrl = ({ hidden, shown }: { hidden?: string; shown?: string }) => {
  const search = new URLSearchParams();
  if (hidden) search.set("hide_columns", hidden);
  if (shown) search.set("show_columns", shown);

  window.history.replaceState(null, "", `${window.location.pathname}?${search}`);
};

const renderRelationshipTable = () =>
  render(
    <RelationshipTable
      relationshipSchema={peerSchema}
      parentId="device-1"
      parentKind={PARENT_KIND}
      relationshipName={RELATIONSHIP_NAME}
    />
  );

describe("RelationshipTable columns", () => {
  let nodeSchemasBeforeSuite: NodeSchema[];

  beforeAll(() => {
    nodeSchemasBeforeSuite = store.get(nodeSchemasAtom);
    store.set(nodeSchemasAtom, [parentSchema, peerSchema]);
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, nodeSchemasBeforeSuite);
  });

  beforeEach(() => {
    window.history.replaceState(null, "", window.location.pathname);

    vi.mocked(useObjectRelationships).mockReturnValue({
      data: { pages: [relationshipRows], pageParams: [] },
      fetchNextPage: vi.fn(),
      error: null,
      hasNextPage: false,
      isPending: false,
      isFetchingNextPage: false,
    } as unknown as ReturnType<typeof useObjectRelationships>);

    vi.mocked(useGetRelationshipCount).mockReturnValue({
      data: relationshipRows.length,
    } as unknown as ReturnType<typeof useGetRelationshipCount>);

    vi.mocked(useGetObjectPermissions).mockReturnValue({
      data: undefined,
    } as unknown as ReturnType<typeof useGetObjectPermissions>);
  });

  test("hides a column the hide param names, header and body cells alike", async () => {
    // GIVEN a link hiding the peer schema's default-visible `description` column
    seedColumnsInUrl({ hidden: "description" });

    // WHEN the relationship tab renders
    const component = await renderRelationshipTable();

    // THEN neither its header nor its values are on screen, while the other column stays
    await expect.element(component.getByText("Name")).toBeVisible();
    await expect.element(component.getByText("Description")).not.toBeInTheDocument();
    await expect.element(component.getByText(DESCRIPTION_VALUE)).not.toBeInTheDocument();
  });

  test("ignores a show param naming a field the relationship fetch never requests", async () => {
    // GIVEN a link asking to reveal the `display: "extra"` attribute
    seedColumnsInUrl({ shown: "internal_note" });

    // WHEN the relationship tab renders
    const component = await renderRelationshipTable();

    // THEN the column stays absent — this table's surface cannot reveal
    await expect.element(component.getByText("Name")).toBeVisible();
    await expect.element(component.getByText("Internal note")).not.toBeInTheDocument();
  });

  // With every rendered field column hidden, the table hands one back rather than rendering none.
  test("keeps a field column when the params ask to hide every one it renders", async () => {
    // GIVEN a link hiding both default columns while revealing the extra one
    seedColumnsInUrl({ hidden: "name,description", shown: "internal_note" });

    // WHEN the relationship tab renders
    const component = await renderRelationshipTable();

    // THEN the first column in display order is handed back instead of an empty table
    await expect.element(component.getByText("Name")).toBeVisible();
    await expect.element(component.getByText("Description")).not.toBeInTheDocument();
  });

  test("offers only the columns this table renders in its toolbar picker", async () => {
    // GIVEN the relationship tab as its hosts render it, with no column params in the link
    const component = await renderRelationshipTable();

    // WHEN opening the toolbar's Columns control
    await component.getByRole("button", { name: "Columns" }).click();

    // THEN the checklist lists the default columns and never the unfetchable extra one
    await expect.element(component.getByRole("menuitem", { name: "Name" })).toBeVisible();
    await expect.element(component.getByRole("menuitem", { name: "Description" })).toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Internal note" }))
      .not.toBeInTheDocument();
  });
});

import { afterAll, afterEach, beforeAll, describe, expect, test, vi } from "vitest";
import { cleanup } from "vitest-browser-react";

import { store } from "@/shared/stores";

import { OBJECT_COLUMN_SURFACE } from "@/entities/nodes/columns/domain/rules/column-surfaces";
import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { ObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { useObjects } from "@/entities/nodes/object/ui/queries/get-objects.query";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../tests/components/render";
import { generatePermission } from "../../../../tests/fake/permission";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../tests/fake/schema";
import {
  RoleManagerObjectTable,
  type RoleManagerObjectTableProps,
} from "./role-manager-object-table";

vi.mock("@/entities/nodes/object/ui/queries/get-objects.query", () => ({
  useObjects: vi.fn(),
}));

vi.mock("@/entities/nodes/object/ui/queries/get-objects-count.query", () => ({
  useObjectsCount: vi.fn(),
}));

vi.mock("@/entities/nodes/object/ui/object-edit/object-item-edit-paginated", () => ({
  default: ({ extraRelationshipNames }: { extraRelationshipNames?: string[] }) => (
    <p>Edit form with {extraRelationshipNames?.join(", ") ?? "no extra relationships"}</p>
  ),
}));

const rolesRelationship = generateRelationshipSchema({
  name: "roles",
  label: "Roles",
  peer: "CoreAccountRole",
  kind: "Generic",
  cardinality: "many",
});

const accountSchema = generateNodeSchema({
  kind: "CoreAccount",
  name: "Account",
  namespace: "Core",
  label: "Account",
  attributes: [
    generateAttributeSchema({ name: "name", label: "Name", kind: "Text" }),
    generateAttributeSchema({ name: "password", label: "Password", kind: "HashedPassword" }),
    generateAttributeSchema({ name: "description", label: "Description", kind: "Text" }),
    generateAttributeSchema({ name: "account_type", label: "Account Type", kind: "Text" }),
    generateAttributeSchema({ name: "status", label: "Status", kind: "Text" }),
  ],
  relationships: [
    generateRelationshipSchema({
      name: "tokens",
      label: "Tokens",
      peer: "InfrahubAccountToken",
      kind: "Component",
      cardinality: "many",
    }),
    generateRelationshipSchema({
      name: "member_of_groups",
      label: "Member Of Groups",
      peer: "CoreAccountGroup",
      kind: "Group",
      cardinality: "many",
    }),
  ],
});

const accountGroupSchema = generateNodeSchema({
  kind: "CoreAccountGroup",
  name: "AccountGroup",
  namespace: "Core",
  label: "Account Group",
});

const accountRoleSchema = generateNodeSchema({
  kind: "CoreAccountRole",
  name: "AccountRole",
  namespace: "Core",
  label: "Account Role",
});

const permissionAttributes = [
  generateAttributeSchema({ name: "action", label: "Action", kind: "Text" }),
  generateAttributeSchema({ name: "identifier", label: "Identifier", kind: "Text" }),
  generateAttributeSchema({ name: "decision", label: "Decision", kind: "Number" }),
];

const globalPermissionSchema = generateNodeSchema({
  kind: "CoreGlobalPermission",
  name: "GlobalPermission",
  namespace: "Core",
  label: "Global permission",
  attributes: permissionAttributes,
  relationships: [rolesRelationship],
});

const objectPermissionSchema = generateNodeSchema({
  kind: "CoreObjectPermission",
  name: "ObjectPermission",
  namespace: "Core",
  label: "Object permission",
  attributes: permissionAttributes,
  relationships: [rolesRelationship],
});

const accountTableProps: RoleManagerObjectTableProps = {
  attributeNames: ["name", "description", "account_type", "status"],
  relationshipNames: ["member_of_groups"],
};

const permissionTableProps: RoleManagerObjectTableProps = {
  attributeNames: ["action", "decision"],
  relationshipNames: ["roles"],
};

const alice: NodeObject = {
  id: "account-1",
  __typename: "CoreAccount",
  display_label: "Alice",
  name: { value: "Alice" },
  description: { value: "Network engineer" },
  account_type: { value: "User" },
  status: { value: "active" },
  member_of_groups: {
    edges: [
      { node: { id: "group-1", __typename: "CoreAccountGroup", display_label: "Operators" } },
    ],
  },
};

const generatePermissionRow = (kind: string, decision: number): NodeObject => ({
  id: "permission-1",
  __typename: kind,
  display_label: "global:edit_default_branch",
  action: { value: "edit_default_branch" },
  decision: { value: decision },
  roles: {
    edges: [{ node: { id: "role-1", __typename: "CoreAccountRole", display_label: "Admin" } }],
  },
});

const mockObjects = ({
  rows = [],
  error = null,
}: {
  rows?: NodeObject[];
  error?: Error | null;
}) => {
  vi.mocked(useObjects).mockReturnValue({
    data: { pages: [rows], pageParams: [] },
    error,
    fetchNextPage: vi.fn(),
    hasNextPage: false,
    isPending: false,
    isFetchingNextPage: false,
  } as unknown as ReturnType<typeof useObjects>);
  vi.mocked(useObjectsCount).mockReturnValue({
    data: rows.length,
  } as unknown as ReturnType<typeof useObjectsCount>);
};

const renderTable = (
  schema: ModelSchema,
  props: RoleManagerObjectTableProps,
  filters: Filter[] = []
) =>
  render(
    <ObjectTableContext
      value={{
        filters,
        setFilters: vi.fn(),
        baseSchema: schema,
        selectedSchema: schema,
        permission: generatePermission(),
        columnSurface: OBJECT_COLUMN_SURFACE,
        supportsColumnVisibility: false,
      }}
    >
      <RoleManagerObjectTable {...props} />
    </ObjectTableContext>
  );

const getButtonLabels = () =>
  Array.from(document.querySelectorAll("button")).map((button) => button.textContent);

const getMenuItemLabels = () =>
  Array.from(document.querySelectorAll('[role="menu"] [role="menuitem"]')).map(
    (item) => item.textContent
  );

const getLastObjectsQuery = () => vi.mocked(useObjects).mock.lastCall?.[0];

const getLastCountQuery = () => vi.mocked(useObjectsCount).mock.lastCall?.[0];

const initialNodeSchemas = store.get(nodeSchemasAtom);

describe("RoleManagerObjectTable", () => {
  beforeAll(() => {
    store.set(nodeSchemasAtom, [
      accountSchema,
      accountGroupSchema,
      accountRoleSchema,
      globalPermissionSchema,
      objectPermissionSchema,
    ]);
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  afterEach(async () => {
    // A sort written to the URL re-renders the table, so it must be gone before the mocks reset.
    await cleanup();
    vi.resetAllMocks();
    window.history.replaceState(null, "", window.location.pathname);
  });

  test("shows the listed attributes in schema order, then the listed relationships, without a name column", async () => {
    // GIVEN
    mockObjects({ rows: [] });

    // WHEN
    const component = await renderTable(accountSchema, accountTableProps);

    // THEN
    await expect.element(component.getByText("No Account found")).toBeVisible();
    expect(getButtonLabels()).toEqual([
      "Description",
      "Account Type",
      "Status",
      "Member Of Groups",
    ]);
  });

  test("fetches only the listed attributes and relationships", async () => {
    // GIVEN
    mockObjects({ rows: [] });

    // WHEN
    await renderTable(accountSchema, accountTableProps);

    // THEN
    const query = getLastObjectsQuery();
    const attributes = query?.getAttributesVisible?.(accountSchema.attributes ?? []);
    const relationships = query?.getRelationshipsVisible?.(accountSchema.relationships ?? []);
    expect(attributes?.map(({ name }) => name)).toEqual([
      "name",
      "description",
      "account_type",
      "status",
    ]);
    expect(relationships?.map(({ name }) => name)).toEqual(["member_of_groups"]);
  });

  test("renders a row with its label, attribute values and relationship peers", async () => {
    // GIVEN
    mockObjects({ rows: [alice] });

    // WHEN
    const component = await renderTable(accountSchema, accountTableProps);

    // THEN
    await expect.element(component.getByRole("link", { name: "Alice" })).toBeVisible();
    await expect.element(component.getByText("Network engineer")).toBeVisible();
    await expect.element(component.getByRole("link", { name: "Operators" })).toBeVisible();
    await expect.element(component.getByTestId("actions-cell-Alice")).toBeVisible();
  });

  test("renders a row whose relationship data is missing", async () => {
    // GIVEN
    const { member_of_groups: _, ...aliceWithoutGroups } = alice;
    mockObjects({ rows: [aliceWithoutGroups] });

    // WHEN
    const component = await renderTable(accountSchema, accountTableProps);

    // THEN
    await expect.element(component.getByRole("link", { name: "Alice" })).toBeVisible();
    await expect.element(component.getByText("Network engineer")).toBeVisible();
  });

  test.each([
    { schema: objectPermissionSchema, decision: 6, label: "Allow in all branches" },
    { schema: globalPermissionSchema, decision: 1, label: "Deny" },
  ])(
    "shows the $schema.kind decision label between the attributes and the relationships",
    async ({ schema, decision, label }) => {
      // GIVEN
      mockObjects({ rows: [generatePermissionRow(schema.kind!, decision)] });

      // WHEN
      const component = await renderTable(schema, permissionTableProps);

      // THEN
      await expect.element(component.getByText(label, { exact: true })).toBeVisible();
      expect(getButtonLabels().slice(0, 3)).toEqual(["Action", "Decision", "Roles"]);
    }
  );

  test("opens the decision filter from the decision column header", async () => {
    // GIVEN
    mockObjects({ rows: [] });
    const component = await renderTable(objectPermissionSchema, permissionTableProps);

    // WHEN
    await component.getByRole("button", { name: "Decision" }).click();

    // THEN
    await expect.element(component.getByText("Filter by Decision")).toBeVisible();
  });

  test.each([
    { schema: objectPermissionSchema, label: "Deny everywhere", value: 1 },
    { schema: objectPermissionSchema, label: "Allow on other branches", value: 4 },
    { schema: globalPermissionSchema, label: "Allow", value: 6 },
  ])(
    "sends $label as decision $value to both $schema.kind queries",
    async ({ schema, label, value }) => {
      // GIVEN
      mockObjects({ rows: [] });
      const filters = [{ name: "decision__value", value: label }];

      // WHEN
      await renderTable(schema, permissionTableProps, filters);

      // THEN
      expect(getLastObjectsQuery()?.filters).toEqual([{ name: "decision__value", value }]);
      expect(getLastCountQuery()?.filters).toEqual([{ name: "decision__value", value }]);
    }
  );

  test("leaves the filters unchanged for a kind without decision options", async () => {
    // GIVEN
    mockObjects({ rows: [] });
    const filters = [{ name: "decision__value", value: "Deny" }];

    // WHEN
    await renderTable(accountSchema, accountTableProps, filters);

    // THEN
    expect(getLastObjectsQuery()?.filters).toEqual([{ name: "decision__value", value: "Deny" }]);
    expect(getLastCountQuery()?.filters).toEqual([{ name: "decision__value", value: "Deny" }]);
  });

  test("requests the objects in the sort order set in the URL", async () => {
    // GIVEN
    mockObjects({ rows: [] });
    window.history.replaceState(null, "", `${window.location.pathname}?sort=status__value__desc`);

    // WHEN
    await renderTable(accountSchema, accountTableProps);

    // THEN
    expect(getLastObjectsQuery()?.sort).toEqual([{ field: "status__value", direction: "DESC" }]);
  });

  test("offers sort and filter entries but no hide entry in an attribute column header", async () => {
    // GIVEN
    mockObjects({ rows: [] });
    const component = await renderTable(accountSchema, accountTableProps);

    // WHEN
    await component.getByRole("button", { name: "Description" }).click();

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Filter" })).toBeVisible();
    expect(getMenuItemLabels()).toEqual(["Sort ascending", "Sort descending", "Filter"]);
  });

  test("requests the objects in the order chosen from a column header", async () => {
    // GIVEN
    mockObjects({ rows: [] });
    const component = await renderTable(accountSchema, accountTableProps);
    await component.getByRole("button", { name: "Description" }).click();

    // WHEN
    await component.getByRole("menuitem", { name: "Sort descending" }).click();

    // THEN
    await expect
      .poll(() => getLastObjectsQuery()?.sort)
      .toEqual([{ field: "description__value", direction: "DESC" }]);
  });

  test.each([
    {
      name: "the given relationships",
      editRelationshipNames: ["member_of_groups"],
      expected: "Edit form with member_of_groups",
    },
    {
      name: "no extra relationships",
      editRelationshipNames: undefined,
      expected: "Edit form with no extra relationships",
    },
  ])("loads $name in the row Edit form", async ({ editRelationshipNames, expected }) => {
    // GIVEN
    mockObjects({ rows: [alice] });
    const component = await renderTable(accountSchema, {
      ...accountTableProps,
      editRelationshipNames,
    });
    await component.getByTestId("actions-cell-Alice").click();

    // WHEN
    await component.getByRole("menuitem", { name: "Edit" }).click();

    // THEN
    await expect.element(component.getByText(expected)).toBeVisible();
  });

  test("shows the query error instead of the table", async () => {
    // GIVEN
    mockObjects({ error: new Error("Permission query failed") });

    // WHEN
    const component = await renderTable(globalPermissionSchema, permissionTableProps);

    // THEN
    await expect.element(component.getByText("Permission query failed")).toBeVisible();
    expect(getButtonLabels()).toEqual([]);
  });
});

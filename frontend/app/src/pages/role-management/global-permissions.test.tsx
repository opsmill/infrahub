import { afterAll, afterEach, beforeAll, describe, expect, test, vi } from "vitest";
import { cleanup } from "vitest-browser-react";

import { store } from "@/shared/stores";

import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { useObjects } from "@/entities/nodes/object/ui/queries/get-objects.query";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../tests/components/render";
import { generatePermission } from "../../../tests/fake/permission";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../tests/fake/schema";
import { Component as GlobalPermissionsPage } from "./global-permissions";

vi.mock("@/entities/nodes/object/ui/queries/get-objects.query", () => ({
  useObjects: vi.fn(),
}));

vi.mock("@/entities/nodes/object/ui/queries/get-objects-count.query", () => ({
  useObjectsCount: vi.fn(),
}));

vi.mock("@/entities/permission/ui/queries/get-object-permissions.query", () => ({
  useGetObjectPermissions: vi.fn(),
}));

const globalPermissionSchema = generateNodeSchema({
  kind: "CoreGlobalPermission",
  name: "GlobalPermission",
  namespace: "Core",
  label: "Global permission",
  attributes: [
    generateAttributeSchema({ name: "action", label: "Action", kind: "Text" }),
    generateAttributeSchema({ name: "decision", label: "Decision", kind: "Number" }),
  ],
  relationships: [
    generateRelationshipSchema({
      name: "roles",
      label: "Roles",
      peer: "CoreAccountRole",
      kind: "Generic",
      cardinality: "many",
    }),
  ],
});

const accountRoleSchema = generateNodeSchema({
  kind: "CoreAccountRole",
  name: "AccountRole",
  namespace: "Core",
  label: "Account Role",
});

const denyPermission: NodeObject = {
  id: "permission-1",
  __typename: "CoreGlobalPermission",
  display_label: "global:edit_default_branch:deny",
  action: { value: "edit_default_branch" },
  decision: { value: 1 },
  roles: {
    edges: [{ node: { id: "role-1", __typename: "CoreAccountRole", display_label: "Admin" } }],
  },
};

const initialNodeSchemas = store.get(nodeSchemasAtom);

describe("Global permissions page", () => {
  beforeAll(() => {
    store.set(nodeSchemasAtom, [globalPermissionSchema, accountRoleSchema]);
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  afterEach(async () => {
    // A sort written to the URL re-renders the page, so it must be gone before the mocks reset.
    await cleanup();
    vi.resetAllMocks();
    window.history.replaceState(null, "", window.location.pathname);
  });

  test("lists the permissions in the sort order the toolbar shows", async () => {
    // GIVEN
    vi.mocked(useGetObjectPermissions).mockReturnValue({
      data: generatePermission(),
      error: null,
      isPending: false,
    } as unknown as ReturnType<typeof useGetObjectPermissions>);
    vi.mocked(useObjects).mockReturnValue({
      data: { pages: [[denyPermission]], pageParams: [] },
      error: null,
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isPending: false,
      isFetchingNextPage: false,
    } as unknown as ReturnType<typeof useObjects>);
    vi.mocked(useObjectsCount).mockReturnValue({
      data: 1,
    } as unknown as ReturnType<typeof useObjectsCount>);
    window.history.replaceState(null, "", `${window.location.pathname}?sort=action__value__desc`);

    // WHEN
    const component = await render(<GlobalPermissionsPage />);

    // THEN
    await expect.element(component.getByRole("button", { name: "Sort 1" })).toBeVisible();
    await expect.element(component.getByText("Deny", { exact: true })).toBeVisible();
    expect(vi.mocked(useObjects).mock.lastCall?.[0].sort).toEqual([
      { field: "action__value", direction: "DESC" },
    ]);
  });
});

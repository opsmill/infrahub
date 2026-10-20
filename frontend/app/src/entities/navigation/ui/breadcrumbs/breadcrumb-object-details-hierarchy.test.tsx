import { Breadcrumbs } from "@infrahub/ui";
import { afterAll, afterEach, beforeAll, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import { BreadcrumbObjectDetailsHierarchy } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-object-details-hierarchy";
import { getObjectAncestorsFromApi } from "@/entities/nodes/hierarchy/api/get-object-ancestors-from-api";
import type { NodeCoreWithParent } from "@/entities/nodes/object/domain/model/node";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../tests/components/utils";
import { generateNodeSchema } from "../../../../../tests/fake/schema";

vi.mock("@/entities/nodes/hierarchy/api/get-object-ancestors-from-api");

const COUNTRY_SCHEMA = generateNodeSchema({
  kind: "LocationCountry",
  namespace: "Location",
  name: "Country",
  label: "Country",
});

const EUROPE: NodeCoreWithParent = {
  id: "europe-id",
  __typename: "LocationRegion",
  display_label: "Europe",
  parent: { node: null },
};

const AMERICAS: NodeCoreWithParent = {
  id: "americas-id",
  __typename: "LocationRegion",
  display_label: "Americas",
  parent: { node: null },
};

const BELGIUM: NodeCoreWithParent = {
  id: "belgium-id",
  __typename: "LocationCountry",
  display_label: "Belgium",
  parent: { node: { id: "europe-id", __typename: "LocationRegion", display_label: "Europe" } },
};

function mockAncestors(ancestors: Array<NodeCoreWithParent>) {
  vi.mocked(getObjectAncestorsFromApi).mockResolvedValue({
    data: {
      LocationCountry: {
        edges: [
          { node: { ...BELGIUM, ancestors: { edges: ancestors.map((node) => ({ node })) } } },
        ],
      },
    },
  } as unknown as Awaited<ReturnType<typeof getObjectAncestorsFromApi>>);
}

function renderBreadcrumb() {
  return render(
    <Breadcrumbs>
      <BreadcrumbObjectDetailsHierarchy objectSchema={COUNTRY_SCHEMA} objectId={BELGIUM.id} />
    </Breadcrumbs>
  );
}

describe("BreadcrumbObjectDetailsHierarchy", () => {
  const initialNodeSchemas = store.get(nodeSchemasAtom);

  beforeAll(() => {
    store.set(nodeSchemasAtom, [
      generateNodeSchema({
        kind: "LocationRegion",
        namespace: "Location",
        name: "Region",
        label: "Region",
      }),
      COUNTRY_SCHEMA,
    ]);
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  test("names the other ancestors when the object has more than one parent", async () => {
    // GIVEN
    mockAncestors([AMERICAS, EUROPE]);
    const component = await renderBreadcrumb();
    await expect.element(component.getByRole("link", { name: "Belgium" })).toBeVisible();

    // WHEN
    await initPointerTracking(component.locator);
    await component.getByRole("button", { name: "More than one parent" }).hover();

    // THEN
    await expect
      .element(
        component.getByText(
          "This object or one of its ancestors has more than one parent. The breadcrumb follows only one of them. Other ancestors found: Americas.",
          { exact: true }
        )
      )
      .toBeVisible();
  });

  test("shows no warning when the object has a single parent", async () => {
    // GIVEN
    mockAncestors([EUROPE]);

    // WHEN
    const component = await renderBreadcrumb();

    // THEN
    await expect.element(component.getByRole("link", { name: "Europe" })).toBeVisible();
    expect(component.getByRole("button", { name: "More than one parent" }).query()).toBeNull();
  });
});

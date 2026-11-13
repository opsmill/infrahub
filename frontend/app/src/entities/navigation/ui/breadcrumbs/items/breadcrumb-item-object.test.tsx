import { Breadcrumbs } from "@infrahub/ui";
import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { page } from "vitest/browser";

import { BreadcrumbItemObject } from "@/entities/navigation/ui/breadcrumbs/items/breadcrumb-item-object";
import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { useRelationships } from "@/entities/nodes/relationships/ui/queries/get-relationships.query";

import { render } from "../../../../../../tests/components/render";

vi.mock("@/entities/nodes/relationships/ui/queries/get-relationships.query");
vi.mock("@/entities/schema/ui/hooks/useSchema", () => ({
  useSchema: () => ({ schema: undefined, isGeneric: false }),
}));

const currentDevice: NodeCore = { id: "device-1", __typename: "InfraDevice", display_label: "" };
const otherDevice: NodeCore = { id: "device-2", __typename: "InfraDevice", display_label: "" };
const router: NodeCore = { id: "router-1", __typename: "InfraRouter", display_label: "" };

const renderBreadcrumbAt = (path: string, routePattern: string) => {
  window.history.replaceState({}, "", path);
  return render(
    <Routes>
      <Route
        path={routePattern}
        element={
          <Breadcrumbs>
            <BreadcrumbItemObject node={currentDevice} />
          </Breadcrumbs>
        }
      />
    </Routes>
  );
};

describe("BreadcrumbItemObject switcher", () => {
  const initialPath = window.location.pathname;

  beforeEach(() => {
    // The virtualized list of react-stately 3.x reads process.env, which browser mode does not define.
    vi.stubGlobal("process", { env: {} });
    vi.mocked(useRelationships).mockReturnValue({
      isPending: false,
      data: { pages: [[otherDevice, router]] },
      error: null,
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
    } as unknown as ReturnType<typeof useRelationships>);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.history.replaceState({}, "", initialPath);
  });

  test("keeps the current tab for objects of the same kind only", async () => {
    // GIVEN
    const breadcrumb = await renderBreadcrumbAt(
      "/objects/InfraDevice/device-1/interfaces",
      "/objects/:objectKind/:objectId/*"
    );

    // WHEN
    await breadcrumb.getByRole("button", { name: /Select a different/ }).click();

    // THEN
    await expect
      .element(page.getByRole("option", { name: "device-2" }))
      .toHaveAttribute("href", "/objects/InfraDevice/device-2/interfaces");
    await expect
      .element(page.getByRole("option", { name: "router-1" }))
      .toHaveAttribute("href", "/objects/InfraRouter/router-1");
  });

  test.each([
    ["/resource-manager/device-1/resources/resource-1", "/resource-manager/:resourcePoolId/*"],
    ["/objects/InfraDevice/device-1/convert", "/objects/:objectKind/:objectId/convert"],
    ["/objects/InfraDevice/child-1/interfaces", "/objects/:objectKind/:objectId/*"],
  ])("links to the details tab on %s", async (path, routePattern) => {
    // GIVEN
    const breadcrumb = await renderBreadcrumbAt(path, routePattern);

    // WHEN
    await breadcrumb.getByRole("button", { name: /Select a different/ }).click();

    // THEN
    await expect
      .element(page.getByRole("option", { name: "device-2" }))
      .toHaveAttribute("href", "/objects/InfraDevice/device-2");
  });
});

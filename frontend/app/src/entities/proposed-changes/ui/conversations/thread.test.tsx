import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import { useNodeLabel } from "@/entities/nodes/object/ui/queries/get-display-label.query";
import { PERMISSION_ALLOW_ALL } from "@/entities/permission/domain/model/permission";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../tests/fake/schema";
import { Thread } from "./thread";

vi.mock("@/entities/nodes/object/ui/queries/get-display-label.query");
vi.mock("@/entities/permission/ui/queries/get-object-permissions.query", () => ({
  useGetObjectPermissions: vi.fn(),
}));

const initialUrl = window.location.pathname + window.location.search;

const deviceId = "18a2e83c-5415-e0f3-3399-c51c3c6f3398";

const objectThread = {
  id: "18a3e1d1-efbe-bd53-38db-c51848891c21",
  __typename: "CoreObjectThread",
  display_label: "Thread",
  label: { value: null },
  resolved: { value: false },
  object_path: { value: `data/${deviceId}/description` },
  comments: {
    count: 1,
    edges: [
      {
        node_metadata: {
          created_at: "2026-04-06T21:29:30.290070+00:00",
          created_by: { display_label: "Admin" },
        },
        node: {
          id: "18a3e1d2-0a4c-3d8e-38db-c518a1b2c3d4",
          display_label: "Check the description",
          text: { value: "Check the description" },
        },
      },
    ],
  },
};

describe("Thread", () => {
  const initialNodeSchemas = store.get(nodeSchemasAtom);

  beforeAll(() => {
    store.set(nodeSchemasAtom, [generateNodeSchema({ kind: "InfraDevice" })]);
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  beforeEach(() => {
    vi.mocked(useNodeLabel).mockReturnValue({
      data: { id: deviceId, display_label: "atl1-edge1", __typename: "InfraDevice" },
      isPending: false,
      error: null,
    } as unknown as ReturnType<typeof useNodeLabel>);
    vi.mocked(useGetObjectPermissions).mockReturnValue({
      data: PERMISSION_ALLOW_ALL,
      isPending: false,
    } as unknown as ReturnType<typeof useGetObjectPermissions>);
  });

  afterEach(() => {
    vi.resetAllMocks();
    window.history.replaceState(null, "", initialUrl);
  });

  test("links the object of an object thread to the data tab of its proposed change", async () => {
    // GIVEN
    window.history.replaceState(null, "", "/proposed-changes/18a3c089-085a-ac67-38d1-c5139dd74202");

    // WHEN
    const component = await render(<Thread thread={objectThread} displayContext />);

    // THEN
    await expect
      .element(component.getByRole("link", { name: /atl1-edge1/ }))
      .toHaveAttribute(
        "href",
        `/proposed-changes/18a3c089-085a-ac67-38d1-c5139dd74202/data#${deviceId}`
      );
  });

  test.each([
    ["homepage", "/"],
    ["Activities page", "/activities"],
  ])("shows the object of an object thread without a link on the %s", async (_, pathname) => {
    // GIVEN
    window.history.replaceState(null, "", pathname);

    // WHEN
    const component = await render(<Thread thread={objectThread} displayContext />);

    // THEN
    await expect.element(component.getByText("atl1-edge1")).toBeVisible();
    await expect.element(component.getByRole("link")).not.toBeInTheDocument();
  });
});

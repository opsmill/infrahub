import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { getRackElevationKindsFromApi } from "@/entities/rack-elevation/api/get-rack-elevation-kinds-from-api";
import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";

import { render } from "../../../../../../tests/components/render";
import { generateRackElevationKinds } from "../../../../../../tests/fake/rack-elevation";
import {
  generateCommitsApiResult,
  generateInSyncCommitsResponse,
} from "../../../../../../tests/fake/repository-commit";
import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import { ObjectDetailsTabs } from "./object-details-tabs";

vi.mock("@/entities/repository/api/get-repository-commits-from-api");
vi.mock("@/entities/rack-elevation/api/get-rack-elevation-kinds-from-api");
vi.mock("@/entities/nodes/relationships/ui/queries/get-relationship-count.query", () => ({
  useGetRelationshipCount: () => ({ isPending: false, data: 0 }),
}));

const renderTabs = (kind: string, inheritFrom: string[]) => {
  const objectSchema = generateNodeSchema({ kind, inherit_from: inheritFrom, relationships: [] });
  const objectData: NodeObject = { id: "object-1", __typename: kind };
  return render(<ObjectDetailsTabs objectSchema={objectSchema} objectData={objectData} />);
};

describe("ObjectDetailsTabs", () => {
  beforeEach(() => {
    vi.mocked(getRepositoryCommitsFromApi).mockResolvedValue(
      generateCommitsApiResult(generateInSyncCommitsResponse())
    );
    vi.mocked(getRackElevationKindsFromApi).mockResolvedValue({
      data: { RackElevationKinds: generateRackElevationKinds() },
    });
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  test("shows the Commits tab for a repository", async () => {
    // WHEN
    const component = await renderTabs(REPOSITORY_KIND, [GENERIC_REPOSITORY_KIND]);

    // THEN
    await expect.element(component.getByRole("link", { name: /^Commits/ })).toBeVisible();
  });

  test("shows no Commits tab for an object that is not a repository", async () => {
    // WHEN
    const component = await renderTabs("BuiltinTag", []);

    // THEN
    await expect.element(component.getByRole("link", { name: "Details" })).toBeVisible();
    expect(component.getByRole("link", { name: /^Commits/ }).query()).toBeNull();
    expect(getRepositoryCommitsFromApi).not.toHaveBeenCalled();
  });

  test("shows the Elevation tab for a kind with the rack role", async () => {
    // WHEN
    const component = await renderTabs("LocationRack", []);

    // THEN
    await expect.element(component.getByRole("link", { name: "Elevation" })).toBeVisible();
  });

  test("shows the Elevation tab for a kind that inherits from a generic with the rack role", async () => {
    // GIVEN
    vi.mocked(getRackElevationKindsFromApi).mockResolvedValue({
      data: { RackElevationKinds: [{ kind: "LocationRackLike", role: "RACK" }] },
    });

    // WHEN
    const component = await renderTabs("LocationCabinet", ["LocationRackLike"]);

    // THEN
    await expect.element(component.getByRole("link", { name: "Elevation" })).toBeVisible();
  });

  test("shows no Elevation tab for a kind without the rack role", async () => {
    // WHEN
    const component = await renderTabs("DcimDevice", []);

    // THEN
    await expect.element(component.getByRole("link", { name: "Details" })).toBeVisible();
    await vi.waitFor(() => expect(getRackElevationKindsFromApi).toHaveBeenCalled());
    expect(component.getByRole("link", { name: "Elevation" }).query()).toBeNull();
  });

  test("shows no Elevation tab when no kind has the rack role", async () => {
    // GIVEN
    vi.mocked(getRackElevationKindsFromApi).mockResolvedValue({ data: { RackElevationKinds: [] } });

    // WHEN
    const component = await renderTabs("LocationRack", []);

    // THEN
    await expect.element(component.getByRole("link", { name: "Details" })).toBeVisible();
    await vi.waitFor(() => expect(getRackElevationKindsFromApi).toHaveBeenCalled());
    expect(component.getByRole("link", { name: "Elevation" }).query()).toBeNull();
  });
});

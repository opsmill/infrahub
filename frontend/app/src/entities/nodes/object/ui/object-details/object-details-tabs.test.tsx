import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";

import { render } from "../../../../../../tests/components/render";
import {
  generateCommitsApiResult,
  generateInSyncCommitsResponse,
} from "../../../../../../tests/fake/repository-commit";
import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import { ObjectDetailsTabs } from "./object-details-tabs";

vi.mock("@/entities/repository/api/get-repository-commits-from-api");
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

  test("keeps the Commits tab outside the scrolling tabs of a repository", async () => {
    // WHEN
    const component = await renderTabs(REPOSITORY_KIND, [GENERIC_REPOSITORY_KIND]);

    // THEN
    const pinned = component.getByTestId("object-details-pinned-tab");
    await expect.element(pinned.getByRole("link", { name: /^Commits/ })).toBeVisible();
    const scrolledTabs = component.getByTestId("object-details-tabs").getByRole("link");
    await expect.element(scrolledTabs.first()).toHaveAccessibleName("Details");
    expect(
      component.container.querySelector(
        "[data-radix-scroll-area-viewport] a[href$='repository_commits']"
      )
    ).toBeNull();
  });

  test("keeps every tab of another object in the scrolling tab bar", async () => {
    // WHEN
    const component = await renderTabs("BuiltinTag", []);

    // THEN
    await expect
      .element(component.getByTestId("object-details-tabs").getByRole("link", { name: "Details" }))
      .toBeVisible();
    expect(component.getByTestId("object-details-pinned-tab").query()).toBeNull();
    expect(
      component.container.querySelector(
        "[data-radix-scroll-area-viewport] [data-testid='object-details-tabs']"
      )
    ).not.toBeNull();
  });

  test("shows no Commits tab for an object that is not a repository", async () => {
    // WHEN
    const component = await renderTabs("BuiltinTag", []);

    // THEN
    await expect.element(component.getByRole("link", { name: "Details" })).toBeVisible();
    expect(component.getByRole("link", { name: /^Commits/ }).query()).toBeNull();
    expect(getRepositoryCommitsFromApi).not.toHaveBeenCalled();
  });
});

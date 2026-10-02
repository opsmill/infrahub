import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { getRepositoryCommitStatusFromApi } from "@/entities/repository/api/get-repository-commit-status-from-api";
import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";

import { render } from "../../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import { ObjectDetailsTabs } from "./object-details-tabs";

vi.mock("@/entities/repository/api/get-repository-commit-status-from-api");
vi.mock("@/entities/nodes/relationships/ui/queries/get-relationship-count.query", () => ({
  useGetRelationshipCount: () => ({ isPending: false, data: 0 }),
}));

type StatusApiResult = Awaited<ReturnType<typeof getRepositoryCommitStatusFromApi>>;

const renderTabs = (kind: string, inheritFrom: string[]) => {
  const objectSchema = generateNodeSchema({ kind, inherit_from: inheritFrom, relationships: [] });
  const objectData: NodeObject = { id: "object-1", __typename: kind };
  return render(<ObjectDetailsTabs objectSchema={objectSchema} objectData={objectData} />);
};

describe("ObjectDetailsTabs", () => {
  beforeEach(() => {
    vi.mocked(getRepositoryCommitStatusFromApi).mockResolvedValue({
      data: { InfrahubRepositoryCommits: { condition: "IN_SYNC", pending_count: 0 } },
    } as StatusApiResult);
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
    expect(getRepositoryCommitStatusFromApi).not.toHaveBeenCalled();
  });
});

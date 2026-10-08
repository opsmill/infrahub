import { beforeEach, describe, expect, it, vi } from "vitest";

import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { getRepositoryBranchStatusFromApi } from "@/entities/repository/api/get-repository-branch-status-from-api";
import { BRANCHES_LOAD_FAILED } from "@/entities/repository/ui/repository-branches-card/messages";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

import { render } from "../../../../tests/components/render";
import { generateNodeAttributeWithMetadata } from "../../../../tests/fake/node";
import { generatePermission } from "../../../../tests/fake/permission";
import {
  generateRepositoryBranchStatusPayloadAfter,
  generateRepositoryBranchStatusPayloadBefore,
} from "../../../../tests/fake/repository";
import { generateAttributeSchema, generateNodeSchema } from "../../../../tests/fake/schema";
import { RepositoryObjectDetails } from "./repository-object-details";

vi.mock("@/entities/repository/api/get-repository-branch-status-from-api");

// A cell that throws while rendering a row is the failure a rejected query cannot reproduce. It
// throws for one branch only, so a row set without that branch is a recovery rather than a retry.
const POISONED_BRANCH = "feature-auth";

vi.mock("@/entities/repository/ui/repository-branches-card/cells/branch-name-cell", () => ({
  BranchNameCell: ({ name }: { name: string }) => {
    if (name === POISONED_BRANCH) throw new Error("branch name cell failed while rendering");

    return <span>{name}</span>;
  },
}));

const apiMock = vi.mocked(getRepositoryBranchStatusFromApi);

const permission = generatePermission();

const repositorySchema: ModelSchema = generateNodeSchema({
  kind: "CoreRepository",
  name: "Repository",
  namespace: "Core",
  label: "Repository",
  branch: "agnostic",
  inherit_from: ["CoreGenericRepository"],
  attributes: [
    generateAttributeSchema({
      name: "name",
      label: "Name",
      branch: "agnostic",
      order_weight: 1000,
    }),
    generateAttributeSchema({
      name: "commit",
      label: "Commit",
      branch: "local",
      order_weight: 2000,
    }),
  ],
  relationships: [],
});

const objectData: NodeObjectWithMetadata = {
  id: "repository-1",
  display_label: "demo-repository",
  __typename: "CoreRepository",
  name: generateNodeAttributeWithMetadata({ value: "demo-repository" }),
  commit: generateNodeAttributeWithMetadata({ value: "abc1234" }),
};

beforeEach(() => {
  apiMock.mockResolvedValue({
    data: { InfrahubRepositoryBranchStatus: generateRepositoryBranchStatusPayloadBefore() },
  });
});

describe("RepositoryObjectDetails when the branches card throws during render", () => {
  it("still renders both details cards", async () => {
    const component = await render(
      <RepositoryObjectDetails
        objectSchema={repositorySchema}
        objectData={objectData}
        permission={permission}
      />
    );

    await expect.element(component.getByText(BRANCHES_LOAD_FAILED, { exact: true })).toBeVisible();

    await expect.element(component.getByRole("region", { name: "Details" })).toBeVisible();
    await expect
      .element(component.getByRole("region", { name: "On this branch test-branch" }))
      .toBeVisible();
    await expect.element(component.getByText("demo-repository", { exact: true })).toBeVisible();
    await expect.element(component.getByText("abc1234", { exact: true })).toBeVisible();
  });

  it("shows the rows again once a row set without the failing branch arrives", async () => {
    // GIVEN a card showing the failure, because the first page holds the branch that throws
    const component = await render(
      <RepositoryObjectDetails
        objectSchema={repositorySchema}
        objectData={objectData}
        permission={permission}
      />
    );
    await expect.element(component.getByText(BRANCHES_LOAD_FAILED, { exact: true })).toBeVisible();

    // WHEN a search returns rows that none of them throws on
    apiMock.mockResolvedValue({
      data: { InfrahubRepositoryBranchStatus: generateRepositoryBranchStatusPayloadAfter() },
    });
    await component.getByRole("searchbox", { name: "Search branches" }).fill("release");

    // THEN the card recovers rather than staying failed until the repository or branch changes
    await expect.element(component.getByText("release-2-0", { exact: true })).toBeVisible();
    expect(component.getByText(BRANCHES_LOAD_FAILED, { exact: true }).elements()).toHaveLength(0);
  });
});
